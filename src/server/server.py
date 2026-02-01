import socket
import threading

# Configuration
HOST = '127.0.0.1'
PORT = 65432

# Shared State
clients = {} # Mapping of socket objects to usernames (or addresses)
clients_lock = threading.Lock()

def broadcast(message, sender_socket=None):
    """Sends a message to all connected clients except the sender."""
    with clients_lock:
        for client_sock in clients:
            if client_sock != sender_socket:
                try:
                    client_sock.sendall(message.encode('utf-8'))
                except Exception as e:
                    print(f"Error broadcasting to a client: {e}")

def handle_client(client_socket, client_address):
    """Main loop for handling an individual client connection."""
    print(f"[NEW CONNECTION] {client_address} connected.")
    
    with clients_lock:
        clients[client_socket] = client_address

    try:
        while True:
            # Blocking call to receive data
            data = client_socket.recv(1024)
            if not data:
                break
            
            message = data.decode('utf-8')
            print(f"[{client_address}] {message}")
            
            # Broadcast the received message to everyone else
            broadcast(f"Client {client_address}: {message}", sender_socket=client_socket)
            
    except ConnectionResetError:
        print(f"[DISCONNECT] {client_address} reset the connection.")
    finally:
        # Graceful Disconnect
        with clients_lock:
            if client_socket in clients:
                del clients[client_socket]
        
        client_socket.close()
        print(f"[DISCONNECT] {client_address} disconnected.")
        broadcast(f"Client {client_address} has left the chat.")

def start_server():
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind((HOST, PORT))
    server_socket.listen()
    
    print(f"[LISTENING] Server is listening on {HOST}:{PORT}")
    
    try:
        while True:
            # Main thread blocks here waiting for new connections
            client_socket, client_address = server_socket.accept()
            
            # Problem 1 Requirement: One thread per connected client
            thread = threading.Thread(target=handle_client, args=(client_socket, client_address))
            thread.daemon = True # Allows server to exit even if threads are running
            thread.start()
            print(f"[ACTIVE CONNECTIONS] {threading.active_count() - 1}")
    except KeyboardInterrupt:
        print("\n[SHUTTING DOWN] Server is stopping.")
    finally:
        server_socket.close()

if __name__ == "__main__":
    start_server()