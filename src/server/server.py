import socket
import threading
import bcrypt

# Configuration
HOST = '127.0.0.1'
PORT = 65432

# In-memory "Database" for testing (Problem 2)
# Format: { username: hashed_password }
user_db = {
    "abhijna": bcrypt.hashpw("kgp123".encode(), bcrypt.gensalt()),
    "gemini": bcrypt.hashpw("password123".encode(), bcrypt.gensalt())
}

# Active Sessions: { username: socket_object }
active_sessions = {}
sessions_lock = threading.Lock()

def broadcast(message, sender_socket=None):
    """Sends a message to all currently active authenticated users."""
    with sessions_lock:
        for user_sock in list(active_sessions.values()):
            if user_sock != sender_socket:
                try:
                    user_sock.sendall(f"{message}\n".encode())
                except:
                    # If sending fails, the socket is likely closed
                    pass

def handle_client(client_socket, addr):
    username = None
    try:
        # --- Problem 2: Authentication Phase ---
        while True:
            client_socket.sendall(b"AUTH_REQUIRED: Please login using 'LOGIN <username> <password>'\n")
            data = client_socket.recv(1024).decode().strip()
            if not data:
                return

            parts = data.split()
            if not parts:
                continue
                
            command = parts[0].upper() 

            if len(parts) == 3 and command == "LOGIN":
                input_user, input_pass = parts[1], parts[2]

                # Check if user exists and password is correct
                if input_user in user_db and bcrypt.checkpw(input_pass.encode(), user_db[input_user]):
                    
                    # --- Problem 3: Force Logout Policy ---
                    with sessions_lock:
                        if input_user in active_sessions:
                            old_sock = active_sessions[input_user]
                            try:
                                # Notify the old client before closing
                                old_sock.sendall(b"FORCED_LOGOUT: Your account logged in from another location.\n")
                                old_sock.close()
                            except:
                                pass
                            print(f"[AUTH] Forced logout for user: {input_user}")
                        
                        # Establish new session
                        active_sessions[input_user] = client_socket
                        username = input_user
                    
                    client_socket.sendall(f"AUTH_SUCCESS: Welcome {username}!\n".encode())
                    broadcast(f"SYSTEM: {username} has joined the chat.")
                    break
                else:
                    client_socket.sendall(b"AUTH_FAILED: Invalid username or password.\n")
            else:
                client_socket.sendall(b"ERROR: Invalid command. Format: LOGIN <username> <password>\n")

        # --- Problem 1 & 3: Chat Phase ---
        while True:
            # 1. Blocking wait for data
            data = client_socket.recv(1024)
            if not data:
                break

            # 2. VALIDITY CHECK (The "Force Logout" Thread Killer)
            # If a newer thread has taken over this username, this socket 
            # will no longer match the one in active_sessions.
            with sessions_lock:
                if active_sessions.get(username) != client_socket:
                    print(f"[DEBUG] Thread for {username} (old session) exiting.")
                    return # Exit function/thread immediately

            msg = data.decode().strip()
            if msg:
                print(f"[{username}] {msg}")
                broadcast(f"{username}: {msg}", sender_socket=client_socket)

    except (ConnectionResetError, BrokenPipeError):
        print(f"[INFO] Connection with {addr} was reset.")
    except Exception as e:
        print(f"[ERROR] {addr} error: {e}")
    finally:
        # Cleanup session only if this specific socket is still the "official" one
        with sessions_lock:
            if username and active_sessions.get(username) == client_socket:
                del active_sessions[username]
                # Only broadcast "left the chat" if they weren't forced out
                broadcast(f"SYSTEM: {username} has left the chat.")
        
        try:
            client_socket.close()
        except:
            pass
        print(f"[DISCONNECT] {addr} disconnected.")

def start_server():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((HOST, PORT))
    server.listen()
    print(f"[*] Server listening on {HOST}:{PORT}")

    while True:
        try:
            conn, addr = server.accept()
            # Problem 1: One thread per client
            thread = threading.Thread(target=handle_client, args=(conn, addr))
            thread.daemon = True
            thread.start()
        except KeyboardInterrupt:
            break

if __name__ == "__main__":
    start_server()