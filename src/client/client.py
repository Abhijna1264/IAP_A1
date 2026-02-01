import socket
import threading

HOST = '127.0.0.1'
PORT = 65432

def receive_messages(sock):
    """Thread function to listen for messages from the server."""
    while True:
        try:
            message = sock.recv(1024).decode('utf-8')
            if message:
                print(f"\n{message}")
                print("> ", end="")
            else:
                break
        except:
            print("[ERROR] Connection lost.")
            break

def start_client():
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client_socket.connect((HOST, PORT))
    
    # Start thread to receive messages
    threading.Thread(target=receive_messages, args=(client_socket,), daemon=True).start()
    
    print("Connected to the server. Type your messages below:")
    try:
        while True:
            msg = input("> ")
            if msg.lower() == 'exit':
                break
            client_socket.sendall(msg.encode('utf-8'))
    except KeyboardInterrupt:
        pass
    finally:
        client_socket.close()

if __name__ == "__main__":
    start_client()