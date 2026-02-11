# ============================================================
# client.py
# Internet Architecture & Protocols - Assignment 1
# Threaded TLS Client
# ============================================================

import socket
import ssl
import threading
from datetime import datetime
import sys

HOST = "127.0.0.1"
PORT = 65432
CERT_FILE = "server.crt"


def ts():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# ------------------ Receiver Thread ------------------
def receive_messages(sock):
    while True:
        try:
            data = sock.recv(4096)
            if not data:
                print(f"\n[{ts()}] [DISCONNECTED] Server closed connection")
                break

            print(f"\n[{ts()}] [RECEIVED] {data.decode().strip()}")
            print("> ", end="", flush=True)

        except Exception as e:
            print(f"\n[{ts()}] [RECEIVER ERROR] {e}")
            break


# ------------------ Client Entry ------------------
def start_client():
    context = ssl.create_default_context(cafile=CERT_FILE)
    context.check_hostname = False
    context.verify_mode = ssl.CERT_REQUIRED

    raw_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock = context.wrap_socket(raw_sock, server_hostname="chatserver")

    try:
        sock.connect((HOST, PORT))
    except Exception as e:
        print(f"[ERROR] {e}")
        return

    print(f"[{ts()}] [CONNECTED] Secure TLS connection established")

    threading.Thread(
        target=receive_messages,
        args=(sock,),
        daemon=True
    ).start()

    try:
        while True:
            msg = input("> ").strip()

            if not msg:
                continue
        
            # Manual logout command
            if msg.lower() in {"/quit", "/exit"}:
                print(f"[{ts()}] [CLIENT] Logout requested")
                sock.sendall(b"/quit\n")
                break

            sock.sendall((msg + "\n").encode())
            print(f"[{ts()}] [SENT] {msg}")

    except KeyboardInterrupt:
        print(f"\n[{ts()}] [CLIENT] Ctrl+C pressed")

    finally:
        sock.close()
        print(f"[{ts()}] [CLIENT CLOSED]")
        sys.exit(0)


if __name__ == "__main__":
    start_client()
