# client.py - PLAIN TCP Client (Phase 1 & 2)
import tkinter as tk
from tkinter import scrolledtext, simpledialog
import socket
import threading
import time
from utils.protocol_helpers import send_message, recv_message

# --- Configuration and State ---
HOST = '127.0.0.1'
PORT = 8080
GLOBAL_USER_ID = "Unauthenticated"
client_socket = None

class NotepadClientApp:
    def __init__(self, master):
        self.master = master
        master.title("Collaborative Notepad")

        self.message_queue = []

        # --- Top Button Frame (File Operations) ---
        button_frame = tk.Frame(master)
        button_frame.pack(fill='x', padx=10, pady=(10, 0))

        tk.Button(button_frame, text="Save File", command=self.send_save_command).pack(side=tk.LEFT, padx=5)
        tk.Button(button_frame, text="New File", command=self.send_new_file_command).pack(side=tk.LEFT, padx=5)

        # --- Text Area Setup ---
        self.text_area = scrolledtext.ScrolledText(master, wrap=tk.WORD, undo=True) # Added undo=True for better UX
        self.text_area.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)
        self.text_area.bind('<KeyRelease>', self.on_text_change)

        # --- Chat UI Setup ---
        chat_frame = tk.LabelFrame(master, text="Real-Time Chat & Notifications")
        chat_frame.pack(padx=10, pady=5, fill='x')

        self.chat_area = scrolledtext.ScrolledText(chat_frame, wrap=tk.WORD, height=6, state=tk.DISABLED, bg='#f0f0f0')
        self.chat_area.pack(padx=5, pady=5, fill=tk.X)

        chat_input_frame = tk.Frame(chat_frame)
        chat_input_frame.pack(fill='x', padx=5, pady=5)

        self.chat_input = tk.Entry(chat_input_frame)
        self.chat_input.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.chat_input.bind('<Return>', lambda event: self.send_chat())

        send_button = tk.Button(chat_input_frame, text="Send", command=self.send_chat)
        send_button.pack(side=tk.RIGHT)

        # --- Status Frame ---
        status_frame = tk.Frame(master)
        status_frame.pack(fill='x', padx=10)
        self.status_label = tk.Label(status_frame, text="Status: Disconnected", fg="red")
        self.status_label.pack(side=tk.LEFT)

        self.connect_button = tk.Button(status_frame, text="Connect", command=self.connect_to_server)
        self.connect_button.pack(side=tk.RIGHT)

        # Start the periodic check for incoming messages (Crucial for Tkinter concurrency)
        self.master.after(100, self.process_incoming_messages) 

    # --- Utility Methods ---
    def append_to_chat(self, text, user="SYSTEM", color="black"):
        """Safely updates the chat area with color coding."""
        self.chat_area.config(state=tk.NORMAL)

        # Define tags for user colors and system messages
        user_tag = f"user_{user}"
        if not self.chat_area.tag_cget(user_tag, 'foreground'):
            # Assign a simple color for user name
            color_map = {"SYSTEM": "red", "NOTIFICATION": "darkorange", "Alice": "blue", "Bob": "green"}
            self.chat_area.tag_config(user_tag, foreground=color_map.get(user, color))

        # Insert message
        self.chat_area.insert(tk.END, f"[{time.strftime('%H:%M:%S')}] ", "time")
        self.chat_area.insert(tk.END, f"<{user}>: ", user_tag)
        self.chat_area.insert(tk.END, f"{text}\n")

        self.chat_area.yview(tk.END) 
        self.chat_area.config(state=tk.DISABLED)

    # --- File/Chat Commands ---
    def send_save_command(self):
        if client_socket:
            send_message(client_socket, {"type": "SAVE", "user": GLOBAL_USER_ID})

    def send_new_file_command(self):
        if client_socket:
            send_message(client_socket, {"type": "NEW_FILE", "user": GLOBAL_USER_ID})

    def send_chat(self, event=None):
        if client_socket:
            text = self.chat_input.get()
            if text.strip():
                send_message(client_socket, {"type": "CHAT", "text": text})
                self.chat_input.delete(0, tk.END)
        return "break"

    # --- Core Network Logic ---
    def connect_to_server(self):
        # ... (Logic to ask for username and start connection thread) ...
        username = simpledialog.askstring("Login", "Enter your username:")
        if not username:
            return

        global GLOBAL_USER_ID
        GLOBAL_USER_ID = username
        self.status_label.config(text="Status: Connecting...", fg="orange")
        self.master.update()

        threading.Thread(target=self._start_connection).start()

    def _start_connection(self):
        # ... (Plain TCP Connection Logic) ...
        global client_socket
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect((HOST, PORT))
            client_socket = sock 

            send_message(client_socket, {"type": "LOGIN", "user": GLOBAL_USER_ID})

            self.master.after(0, lambda: self.status_label.config(text=f"Status: Connected as {GLOBAL_USER_ID}", fg="green"))

            threading.Thread(target=self._listen_to_server, daemon=True).start()

        except Exception as e:
            error_msg = f"Connection Failed: {e}"
            self.master.after(0, lambda: self.status_label.config(text=error_msg, fg="red"))
            client_socket = None

    def _listen_to_server(self):
        # ... (Threaded listening loop) ...
        while client_socket:
            message = recv_message(client_socket)
            if message is None:
                self.message_queue.append({"type": "DISCONNECT"})
                break
            self.message_queue.append(message)

    def process_incoming_messages(self):
        # ... (Main thread message processing) ...
        while self.message_queue:
            message = self.message_queue.pop(0)
            msg_type = message.get("type")

            if msg_type == "DOC_STATE" or msg_type == "EDIT_UPDATE":
                # Update by replacing the entire content (Phase 1 simplicity)
                current_scroll_pos = self.text_area.yview() 
                self.text_area.delete('1.0', tk.END)
                self.text_area.insert(tk.END, message.get("content", ""))
                self.text_area.yview_moveto(current_scroll_pos[0])

            elif msg_type == "CHAT_MESSAGE":
                # Handle incoming chat message
                user = message.get("user")
                text = message.get("text")
                self.append_to_chat(text, user=user, color="black")

            elif msg_type == "NOTIFICATION":
                # Handle Change Notification feature (e.g., File Saved)
                self.append_to_chat(message.get("message"), user="NOTIFICATION", color="darkorange")

            elif msg_type == "DISCONNECT":
                self.status_label.config(text="Status: Server Disconnected", fg="red")
                global client_socket
                if client_socket: client_socket.close()
                client_socket = None

        self.master.after(100, self.process_incoming_messages)

    # --- GUI Event Handling ---
    def on_text_change(self, event):
        if client_socket:
            current_content = self.text_area.get('1.0', tk.END)
            send_message(client_socket, {"type": "EDIT", "content": current_content, "user": GLOBAL_USER_ID})

# --- Main Execution ---
if __name__ == "__main__":
    root = tk.Tk()
    app = NotepadClientApp(root)
    root.mainloop()