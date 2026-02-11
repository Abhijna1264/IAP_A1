# ============================================================
# server.py
# Internet Architecture & Protocols - Assignment 1
#
# Covers:
# Problem 1: Thread-based TCP server
# Problem 2: Authentication with bcrypt
# Problem 3: Duplicate login handling (Reject policy)
# Problem 4: Chat rooms
# Problem 5: Publish-Subscribe (user subscriptions)
# Problem 6: Redis distributed state + Pub/Sub
# Problem 7: TLS encrypted transport
# Problem 8: Docker-compatible stateless server
# ============================================================

import socket
import ssl
import threading
import bcrypt
import redis
import json
import os
from datetime import datetime
import signal

shutdown_event = threading.Event()

# ------------------ CONFIG ------------------
HOST = "0.0.0.0"
PORT = 65432
SERVER_ID = os.getenv("SERVER_ID", "server1")

# ------------------ REDIS ------------------
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")   # use env variable, default localhost
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))

r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)

# ------------------ LOCAL SOCKET STATE ------------------
local_clients = {}          # username -> socket
lock = threading.Lock()


def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
def print_connected_clients():
    with lock:
        users = list(local_clients.keys())
    print(f"[{now()}] [CONNECTED CLIENTS] {users if users else 'None'}")


# ============================================================
# Problem 6: Redis Pub/Sub Listener
# ============================================================
def redis_listener():
    pubsub = r.pubsub()
    pubsub.subscribe("global_chat")
    print(f"[{now()}] [REDIS] Pub/Sub listener started")

    for msg in pubsub.listen():
        if shutdown_event.is_set():
            break

        if msg["type"] != "message":
            continue

        data = json.loads(msg["data"])
        sender = data["sender"]
        targets = data["targets"]
        text = data["message"]
        ts = data["timestamp"]

        with lock:
            for user in targets:
                if user in local_clients:
                    try:
                        local_clients[user].sendall(
                            f"[{ts}] [{sender}] {text}\n".encode()
                        )
                    except:
                        pass


# ============================================================
# Problem 1–5: Client Handler
# ============================================================
def handle_client(conn, addr):
    #conn.settimeout(30) # detect dead clients (stale sessions)
    username = None
    print(f"[{now()}] [THREAD START] Handling client {addr}")

    try:
        # -------- Authentication --------
        conn.sendall(b"LOGIN <username> <password>\n")
        # data = conn.recv(1024)
        # if not data:
        #     return

        # parts = data.decode().strip().split()
        # buffer = b""
        # while b"\n" not in buffer:
        #     chunk = conn.recv(1024)
        #     if not chunk:
        #         return
        #     buffer += chunk

        # line = buffer.decode().strip()
        # parts = line.split()
        conn_file = conn.makefile("r")

        line = conn_file.readline()
        if not line:
            return

        parts = line.strip().split()


        if len(parts) != 3 or parts[0].upper() != "LOGIN":
            conn.sendall(b"ERROR: Invalid LOGIN format\n")
            return

        _, user, pwd = parts
        user_key = f"users:{user}" #authentication

        # Auto-register
        if not r.exists(user_key):
            hashed = bcrypt.hashpw(pwd.encode(), bcrypt.gensalt()).decode()
            r.hset(user_key, "password", hashed)
            print(f"[{now()}] [REGISTER] New user '{user}'")

        stored_hash = r.hget(user_key, "password").encode()
        if not bcrypt.checkpw(pwd.encode(), stored_hash):
            conn.sendall(b"AUTH_FAILED\n")
            return

        # -------- Duplicate Login --------
        if r.hexists("sessions", user):
            conn.sendall(b"ERROR: User already logged in\n")
            print(f"[{now()}] [DUPLICATE LOGIN] {user}")
            return

        # -------- Session Setup --------
        r.hset("sessions", user, SERVER_ID)
        r.set(f"user_room:{user}", "lobby")
        r.sadd("room:lobby", user)

        with lock:
            local_clients[user] = conn

        username = user
        conn.sendall(b"AUTH_SUCCESS\n")
        print(f"[{now()}] [LOGIN] User '{user}' logged in")

        # -------- Chat Loop --------
        while True:
            try:
                data = conn.recv(4096)
                if not data:
                    break
            except socket.timeout:
                print(f"[{now()}] [TIMEOUT] {username} inactive, closing session")
                break

            msg = data.decode().strip()
            if not msg:
                continue

            print(f"[{now()}] [RECV] {username}: {msg}")

            # Logout command
            if msg == "/quit":
                conn.sendall(b"LOGOUT_SUCCESS\n")
                break
            # -------- Rooms --------
            elif msg.startswith("/join "):
                new_room = msg.split(maxsplit=1)[1]
                old_room = r.get(f"user_room:{username}")

                r.srem(f"room:{old_room}", username)
                r.sadd(f"room:{new_room}", username)
                r.set(f"user_room:{username}", new_room)

                conn.sendall(f"[{now()}] Joined room {new_room}\n".encode())
                print(f"[{now()}] [ROOM] {username} moved {old_room} → {new_room}")
            
            elif msg == "/who":
                with lock:
                    users = list(local_clients.keys())
                conn.sendall(
                    f"[{now()}] Connected users: {', '.join(users) if users else 'None'}\n".encode()
                )


            elif msg == "/leave":
                old_room = r.get(f"user_room:{username}")

                r.srem(f"room:{old_room}", username)
                r.sadd("room:lobby", username)
                r.set(f"user_room:{username}", "lobby")

                conn.sendall(f"[{now()}] Returned to lobby\n".encode())
                print(f"[{now()}] [ROOM] {username} returned to lobby")

            elif msg == "/rooms":
                rooms = sorted({k.split(":")[1] for k in r.scan_iter("room:*")})
                conn.sendall(f"[{now()}] Rooms: {', '.join(rooms)}\n".encode())

            # -------- Subscribe --------
            elif msg.startswith("/subscribe "):
                target = msg.split(maxsplit=1)[1]
                r.sadd(f"subs:{target}", username)
                conn.sendall(f"[{now()}] Subscribed to {target}\n".encode())
                print(f"[{now()}] [SUBSCRIBE] {username} → {target}")

            elif msg.startswith("/unsubscribe "):
                target = msg.split(maxsplit=1)[1]
                r.srem(f"subs:{target}", username)
                conn.sendall(f"[{now()}] Unsubscribed from {target}\n".encode())
                print(f"[{now()}] [UNSUBSCRIBE] {username} → {target}")

            # -------- Publish Message --------
            else:
                room = r.get(f"user_room:{username}")
                room_users = r.smembers(f"room:{room}")
                subs = r.smembers(f"subs:{username}")

                targets = set(room_users) | set(subs)
                targets.discard(username)

                payload = json.dumps({
                    "sender": username,
                    "targets": list(targets),
                    "message": msg,
                    "timestamp": now()
                })

                r.publish("global_chat", payload)
                print(f"[{now()}] [PUBLISH] {username} → {targets}")

    finally:
        # -------- Cleanup --------
        if username and r.hexists("sessions", username):
            r.hdel("sessions", username)

            room = r.get(f"user_room:{username}")
            if room:
                r.srem(f"room:{room}", username)

            with lock:
                local_clients.pop(username, None)

            print(f"[{now()}] [LOGOUT] {username}")
            print_connected_clients()

        conn.close()
        print(f"[{now()}] [DISCONNECT] {addr}")


# ============================================================
# Server Startup
# ============================================================
def shutdown_handler(sig, frame):
    print(f"\n[{now()}] [SERVER SHUTDOWN] Ctrl+C received")
    shutdown_event.set()


def start_server():
    threading.Thread(target=redis_listener, daemon=True).start()

    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain("server.crt", "server.key")

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((HOST, PORT))
    sock.listen()
    sock.settimeout(1.0)

    print(f"[{now()}] [{SERVER_ID}] TLS server listening on port {PORT}")
    print_connected_clients()

    while not shutdown_event.is_set():
        try:
            conn, addr = sock.accept()
        except socket.timeout:
            continue

        print(f"[{now()}] [CONNECT] TCP from {addr}")

        try:
            tls_conn = context.wrap_socket(conn, server_side=True)
            print(f"[{now()}] [TLS] Handshake OK {addr}")
        except ssl.SSLError as e:
            print(f"[{now()}] [TLS ERROR] {addr} {e}")
            conn.close()
            continue

        threading.Thread(
            target=handle_client,
            args=(tls_conn, addr),
            daemon=True
        ).start()


if __name__ == "__main__":
    signal.signal(signal.SIGINT, shutdown_handler)
    start_server()
