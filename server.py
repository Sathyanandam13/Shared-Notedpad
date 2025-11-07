# server.py - Database-Backed Authentication Server (FINAL FIXED VERSION)
import socket
import threading
import os
import time
from secrets import token_hex 
from utils.protocol_helpers import send_message, recv_message
from utils.database import initialize_db, create_user, find_user_by_username
from utils.encryption import check_password

# --- Configuration and State ---
HOST = '127.0.0.1' 
PORT = 8080
DOC_PATH = 'documents/master_doc.txt'

# Shared State
connected_clients = []
doc_lock = threading.Lock() 
current_document = "" 
ACTIVE_SESSIONS = {}  # {session_id: user_id}

def load_document():
    """Loads the document from disk and initializes the DB."""
    global current_document
    os.makedirs('documents', exist_ok=True)
    
    # --- Initialize DB and create test admin user ---
    initialize_db()
    if not find_user_by_username("admin"):
        create_user("admin", "adminpass", is_admin=True)
    
    # Load or initialize document
    if os.path.exists(DOC_PATH):
        with open(DOC_PATH, 'r') as f:
            current_document = f.read()
    else:
        current_document = "Welcome to the Collaborative Notepad!"
        with open(DOC_PATH, 'w') as f:
            f.write(current_document) 

def broadcast_message(message_dict, exclude_sock=None):
    """Sends a message to all connected clients."""
    global connected_clients
    for client_sock, user_id, session_id in list(connected_clients):
        if client_sock != exclude_sock:
            send_message(client_sock, message_dict)

def handle_client(sock):
    """Handles all communication for a single client in its own thread."""
    global current_document, connected_clients, doc_lock, ACTIVE_SESSIONS

    user_id = "UNAUTHENTICATED" 
    session_id = None
    
    with doc_lock:
        connected_clients.append((sock, user_id, session_id))
    
    print(f"New connection from {sock.getpeername()}. Waiting for authentication...")

    while True:
        try:
            message = recv_message(sock)
            if message is None:
                break
            
            msg_type = message.get("type")

            # --- HELLO handshake ---
            if msg_type == "HELLO":
                send_message(sock, {"type": "DOC_STATE", "content": current_document})
                continue
            
            # --- AUTH VALIDATION ---
            if msg_type not in ["LOGIN", "SIGNUP", "HELLO", "LOGOUT"]:
                session_id = message.get("session_id")
                if session_id not in ACTIVE_SESSIONS:
                    send_message(sock, {"type": "AUTH_FAIL", "message": "Authentication required."})
                    break 
                user_id = ACTIVE_SESSIONS[session_id]
            
            # --- SIGNUP ROUTE ---
            if msg_type == "SIGNUP":
                new_user = message.get("user")
                password = message.get("password")
                
                if create_user(new_user, password):
                    send_message(sock, {"type": "AUTH_SUCCESS", "message": "Signup successful! Please log in."})
                else:
                    send_message(sock, {"type": "AUTH_FAIL", "message": "Username already exists."})

            # --- LOGIN ROUTE (FIXED) ---
            elif msg_type == "LOGIN":
                new_id = message.get("user")
                password = message.get("password") 
                
                user_data = find_user_by_username(new_id)
                print(f"[DEBUG] Attempting login for '{new_id}', found in DB: {user_data is not None}")

                if user_data:
                    try:
                        is_valid = check_password(password, user_data['password_hash'])
                    except Exception as e:
                        print(f"[ERROR] check_password failed for {new_id}: {e}")
                        send_message(sock, {"type": "AUTH_FAIL", "message": "Error verifying password."})
                        continue
                else:
                    is_valid = False

                if is_valid:
                    session_id = token_hex(16)
                    with doc_lock:
                        ACTIVE_SESSIONS[session_id] = new_id
                        connected_clients = [
                            (s, new_id, session_id) if s == sock else (s, u, sid)
                            for s, u, sid in connected_clients
                        ]
                        user_id = new_id
                        
                    send_message(sock, {"type": "AUTH_SUCCESS", "session_id": session_id, "user": new_id})
                    print(f"✅ Client {sock.getpeername()} authenticated as {new_id}. Session: {session_id}")
                else:
                    send_message(sock, {"type": "AUTH_FAIL", "message": "Invalid username or password."})
                    print(f"❌ Authentication failed for '{new_id}'. Client remains connected.")
                    continue  # FIXED: do not break connection

            # --- LOGOUT ROUTE ---
            elif msg_type == "LOGOUT":
                print(f"Client {user_id} requested logout. Closing connection.")
                break

            # --- Protected Routes (EDIT, SAVE, NEW_FILE, CHAT) ---
            elif msg_type == "EDIT":
                with doc_lock:
                    current_document = message.get("content", "")
                    broadcast_message({"type": "EDIT_UPDATE", "content": current_document}, exclude_sock=sock)
            
            elif msg_type == "SAVE":
                with doc_lock:
                    with open(DOC_PATH, 'w') as f:
                        f.write(current_document)
                save_msg = f"Document saved by {user_id}."
                broadcast_message({"type": "NOTIFICATION", "message": save_msg})

            elif msg_type == "NEW_FILE":
                with doc_lock:
                    current_document = f"New document started by {user_id} at {time.strftime('%H:%M:%S')}."
                    with open(DOC_PATH, 'w') as f:
                        f.write(current_document)
                broadcast_message({"type": "DOC_STATE", "content": current_document})
                broadcast_message({"type": "NOTIFICATION", "message": f"{user_id} created a new file."})
            
            elif msg_type == "CHAT":
                chat_text = message.get("text", "")
                broadcast_message({"type": "CHAT_MESSAGE", "user": user_id, "text": chat_text})
            
        except Exception as e:
            print(f"Error handling client {user_id} ({sock.getpeername()}): {e}")
            break

    # --- CLEANUP ---
    print(f"Client {user_id} disconnected.")
    session_to_remove = next((sid for sid, uid in ACTIVE_SESSIONS.items() if uid == user_id), None)
    if session_to_remove:
        with doc_lock:
            del ACTIVE_SESSIONS[session_to_remove]
            print(f"Session {session_to_remove} for {user_id} terminated.")
    
    with doc_lock:
        connected_clients = [c for c in connected_clients if c[0] != sock]
    sock.close()

def start_server():
    """Starts the main server listener loop."""
    os.makedirs('documents', exist_ok=True)
    load_document()
    
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((HOST, PORT))
        sock.listen(5)
        print(f"✅ Server listening on {HOST}:{PORT}")
        
        while True:
            try:
                client_sock, addr = sock.accept()
                threading.Thread(target=handle_client, args=(client_sock,), daemon=True).start()
            except KeyboardInterrupt:
                print("\nServer shutting down...")
                break
            except Exception as e:
                print(f"Server acceptance error: {e}")
                break

if __name__ == "__main__":
    start_server()
