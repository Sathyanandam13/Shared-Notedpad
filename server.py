# server.py - PLAIN TCP Server (Phase 1 & 2 - SYNTAX FIXED)
import socket
import threading
import os
import time
from utils.protocol_helpers import send_message, recv_message

# --- Configuration and State ---
HOST = '127.0.0.1' 
PORT = 8080
DOC_PATH = 'documents/master_doc.txt'

# Shared State
connected_clients = []
# Lock to safely control access to shared variables (like the document content) from multiple threads
doc_lock = threading.Lock() 
current_document = "" 

def load_document():
    """Loads the document from disk or initializes a new one."""
    global current_document
    # Ensure the documents folder exists
    os.makedirs('documents', exist_ok=True)
    
    if os.path.exists(DOC_PATH):
        with open(DOC_PATH, 'r') as f:
            current_document = f.read()
    else:
        current_document = "Welcome to the Collaborative Notepad!"
        # Create the file for the first run if it doesn't exist
        with open(DOC_PATH, 'w') as f:
            f.write(current_document) 

def broadcast_message(message_dict, exclude_sock=None):
    """Sends a message to all connected clients."""
    # Note: We iterate over a copy of the list for thread-safety.
    for client_sock, user_id in list(connected_clients):
        if client_sock != exclude_sock:
            send_message(client_sock, message_dict)

def handle_client(sock):
    """
    Handles all communication for a single client in its own thread.
    
    FIX: Declaring current_document as global at the start of this 
    function ensures the scope is correctly set before it's used 
    inside the 'with doc_lock:' blocks.
    """
    global current_document, connected_clients, doc_lock # <--- THE CRITICAL FIX

    # Temporary ID used until the client sends the LOGIN message
    user_id = f"User-{threading.get_ident() % 100}" 
    
    # Add client immediately; update user_id after login message
    connected_clients.append((sock, user_id))
    print(f"New connection from {sock.getpeername()} with temporary ID {user_id}")
    
    # Send initial document state
    send_message(sock, {"type": "DOC_STATE", "content": current_document})

    while True:
        try:
            message = recv_message(sock)
            if message is None:
                break # Connection closed
            
            msg_type = message.get("type")
            
            # --- Shared Document Logic ---
            if msg_type == "EDIT":
                with doc_lock:
                    # 'current_document' is now correctly recognized as global
                    current_document = message.get("content", "")
                    print(f"[{user_id}] Edited document. Broadcasting.")
                    
                    # Broadcast the new content 
                    broadcast_message({"type": "EDIT_UPDATE", "content": current_document}, exclude_sock=sock)
            
            # --- File Operations ---
            elif msg_type == "SAVE":
                with doc_lock:
                    # 'current_document' is recognized as global
                    with open(DOC_PATH, 'w') as f:
                        f.write(current_document)
                
                save_msg = f"Document saved by {user_id}."
                print(save_msg)
                # Send explicit notification to all clients
                broadcast_message({"type": "NOTIFICATION", "message": save_msg})

            elif msg_type == "NEW_FILE":
                with doc_lock:
                    # 'current_document' is recognized as global
                    current_document = f"New document started by {user_id} at {time.strftime('%H:%M:%S')}."
                    with open(DOC_PATH, 'w') as f:
                        f.write(current_document)
                        
                # Broadcast the new empty state to everyone
                broadcast_message({"type": "DOC_STATE", "content": current_document})
                broadcast_message({"type": "NOTIFICATION", "message": f"{user_id} created a new file."})
            
            # --- Chat Logic ---
            elif msg_type == "CHAT":
                chat_text = message.get("text", "")
                print(f"[{user_id}] Chat: {chat_text}")
                # Broadcast the chat message to everyone
                broadcast_message({"type": "CHAT_MESSAGE", "user": user_id, "text": chat_text})
            
            # --- Login/Identity (Runs once) ---
            elif msg_type == "LOGIN":
                new_id = message.get("user")
                
                # Update the user_id in the connected_clients list
                with doc_lock: # Using lock to modify the shared list
                    try:
                        temp_client_tuple = next(c for c in connected_clients if c[0] == sock)
                        connected_clients.remove(temp_client_tuple)
                        connected_clients.append((sock, new_id))
                        user_id = new_id # Update local variable for thread logging
                        print(f"Client {sock.getpeername()} identified as {user_id}")
                    except StopIteration:
                        pass
                    
        except Exception as e:
            print(f"Error handling client {user_id}: {e}")
            break

    # Cleanup
    print(f"Client {user_id} disconnected.")
    # Remove the client from the shared list using the lock
    with doc_lock:
        connected_clients = [c for c in connected_clients if c[0] != sock]
    sock.close()

def start_server():
    """Starts the main server listener loop."""
    # Ensure the documents folder exists and load the initial file
    os.makedirs('documents', exist_ok=True)
    load_document()
    
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        # Allow the port to be reused quickly after the server is stopped
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1) 
        
        sock.bind((HOST, PORT))
        sock.listen(5)
        print(f"Server listening on {HOST}:{PORT}")
        
        while True:
            try:
                client_sock, addr = sock.accept()
                client_handler = threading.Thread(target=handle_client, args=(client_sock,))
                client_handler.start()
            except KeyboardInterrupt:
                print("\nServer shutting down...")
                break
            except Exception as e:
                print(f"Server acceptance error: {e}")
                break

if __name__ == "__main__":
    start_server()