import socket
import threading
import bcrypt

# Configuration
HOST = '127.0.0.1'
PORT = 65432

# ------------------ USER DATABASE (Problem 2) ------------------
user_db = {
    "abhijna": bcrypt.hashpw("kgp123".encode(), bcrypt.gensalt()),
    "gemini": bcrypt.hashpw("password123".encode(), bcrypt.gensalt())
}

# ------------------ ACTIVE SESSIONS (Problem 1 & 3) ------------------
active_sessions = {}          # username -> socket
sessions_lock = threading.Lock()

# ------------------ Problem 4: CHAT ROOMS ------------------
rooms = {"lobby": set()}      # room_name -> set(usernames)
user_room = {}                # username -> room_name
room_lock = threading.Lock()

# ------------------ Problem 5: PUBLISH–SUBSCRIBE ------------------
subscriptions = {}            # publisher -> set(subscribers)
sub_lock = threading.Lock()


# ------------------ BROADCAST (USED ONLY FOR SYSTEM MESSAGES) ------------------
def broadcast(message, sender_socket=None):
    with sessions_lock:
        for sock in active_sessions.values():
            if sock != sender_socket:
                try:
                    sock.sendall(f"{message}\n".encode())
                except:
                    pass


# ------------------ ROOM MESSAGE ------------------
def send_to_room(sender, message):
    with room_lock:
        room = user_room.get(sender)
        recipients = rooms.get(room, set()).copy()

    with sessions_lock:
        for user in recipients:
            if user != sender and user in active_sessions:
                try:
                    active_sessions[user].sendall(
                        f"[{room}] {sender}: {message}\n".encode()
                    )
                except:
                    pass


# ------------------ PUBLISH MESSAGE ------------------
def publish_message(sender, message):
    with sub_lock:
        subs = subscriptions.get(sender, set()).copy()

    with sessions_lock:
        for user in subs:
            if user in active_sessions:
                try:
                    active_sessions[user].sendall(
                        f"[PUB] {sender}: {message}\n".encode()
                    )
                except:
                    pass


# ------------------ CLIENT HANDLER ------------------
def handle_client(client_socket, addr):
    username = None

    try:
        # -------- AUTHENTICATION PHASE (Problem 2 & 3) --------
        while True:
            client_socket.sendall(
                b"AUTH_REQUIRED: LOGIN <username> <password>\n"
            )
            data = client_socket.recv(1024).decode().strip()
            if not data:
                return

            parts = data.split()
            if len(parts) == 3 and parts[0].upper() == "LOGIN":
                input_user, input_pass = parts[1], parts[2]

                if input_user in user_db and bcrypt.checkpw(
                    input_pass.encode(), user_db[input_user]
                ):
                    with sessions_lock:
                        if input_user in active_sessions:
                            old_sock = active_sessions[input_user]
                            try:
                                old_sock.sendall(
                                    b"FORCED_LOGOUT: Logged in elsewhere\n"
                                )
                                old_sock.close()
                            except:
                                pass

                        active_sessions[input_user] = client_socket
                        username = input_user

                    client_socket.sendall(
                        f"AUTH_SUCCESS: Welcome {username}\n".encode()
                    )
                    broadcast(f"SYSTEM: {username} joined the chat")

                    # Default room = lobby (Problem 4)
                    with room_lock:
                        rooms["lobby"].add(username)
                        user_room[username] = "lobby"

                    break
                else:
                    client_socket.sendall(
                        b"AUTH_FAILED: Invalid credentials\n"
                    )
            else:
                client_socket.sendall(
                    b"ERROR: LOGIN <username> <password>\n"
                )

        # -------- CHAT PHASE (Problem 4 & 5) --------
        while True:
            data = client_socket.recv(1024)
            if not data:
                break

            with sessions_lock:
                if active_sessions.get(username) != client_socket:
                    return

            msg = data.decode().strip()
            if not msg:
                continue

            # ----- Room commands -----
            if msg.startswith("/join "):
                room_name = msg.split(maxsplit=1)[1]
                with room_lock:
                    old_room = user_room.get(username)
                    if old_room:
                        rooms[old_room].discard(username)
                    rooms.setdefault(room_name, set()).add(username)
                    user_room[username] = room_name
                client_socket.sendall(
                    f"You joined room: {room_name}\n".encode()
                )

            elif msg == "/leave":
                with room_lock:
                    old_room = user_room.get(username)
                    if old_room:
                        rooms[old_room].discard(username)
                    rooms["lobby"].add(username)
                    user_room[username] = "lobby"
                client_socket.sendall(
                    b"You returned to lobby\n"
                )

            elif msg == "/rooms":
                with room_lock:
                    room_list = ", ".join(rooms.keys())
                client_socket.sendall(
                    f"Rooms: {room_list}\n".encode()
                )

            # ----- Pub–Sub commands -----
            elif msg.startswith("/subscribe "):
                target = msg.split(maxsplit=1)[1]
                with sub_lock:
                    subscriptions.setdefault(target, set()).add(username)
                client_socket.sendall(
                    f"Subscribed to {target}\n".encode()
                )

            elif msg.startswith("/unsubscribe "):
                target = msg.split(maxsplit=1)[1]
                with sub_lock:
                    if target in subscriptions:
                        subscriptions[target].discard(username)
                client_socket.sendall(
                    f"Unsubscribed from {target}\n".encode()
                )

            # ----- Normal message -----
            else:
                print(f"[{username}] {msg}")
                send_to_room(username, msg)
                publish_message(username, msg)

    except Exception as e:
        print(f"[ERROR] {addr}: {e}")

    finally:
        # Cleanup rooms
        with room_lock:
            room = user_room.pop(username, None)
            if room:
                rooms[room].discard(username)

        # Cleanup subscriptions
        with sub_lock:
            subscriptions.pop(username, None)
            for subs in subscriptions.values():
                subs.discard(username)

        # Cleanup session
        with sessions_lock:
            if username and active_sessions.get(username) == client_socket:
                del active_sessions[username]
                broadcast(f"SYSTEM: {username} left the chat")

        try:
            client_socket.close()
        except:
            pass

        print(f"[DISCONNECT] {addr}")


# ------------------ SERVER START ------------------
def start_server():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((HOST, PORT))
    server.listen()
    print(f"[*] Server listening on {HOST}:{PORT}")

    while True:
        try:
            conn, addr = server.accept()
            t = threading.Thread(
                target=handle_client, args=(conn, addr), daemon=True
            )
            t.start()
        except KeyboardInterrupt:
            break


if __name__ == "__main__":
    start_server()
