# client.py - Database-Backed Authentication Client (FINAL FIXED VERSION)
import tkinter as tk
from tkinter import scrolledtext, simpledialog
from tkinter import messagebox as mb
import socket
import threading
import time
from utils.protocol_helpers import send_message, recv_message

# --- Configuration and State ---
HOST = '127.0.0.1'
PORT = 8080
GLOBAL_USER_ID = "UNAUTHENTICATED"
GLOBAL_SESSION_ID = None
client_socket = None


class NotepadClientApp:
    USER_COLORS = ["blue", "green", "purple", "orange", "darkred", "teal", "indigo"]
    user_color_map = {}

    def __init__(self, master):
        self.master = master
        master.title("Collaborative Notepad")

        self.message_queue = []

        # --- Top Button Frame ---
        button_frame = tk.Frame(master)
        button_frame.pack(fill='x', padx=10, pady=(10, 0))

        self.save_btn = tk.Button(button_frame, text="Save File", command=self.send_save_command, state=tk.DISABLED)
        self.save_btn.pack(side=tk.LEFT, padx=5)
        self.new_btn = tk.Button(button_frame, text="New File", command=self.send_new_file_command, state=tk.DISABLED)
        self.new_btn.pack(side=tk.LEFT, padx=5)

        self.signup_btn = tk.Button(button_frame, text="Sign Up", command=self.open_signup_dialog, state=tk.DISABLED)
        self.signup_btn.pack(side=tk.RIGHT, padx=5)
        self.login_btn = tk.Button(button_frame, text="Login", command=self.open_login_dialog_only, state=tk.DISABLED)
        self.login_btn.pack(side=tk.RIGHT, padx=5)

        # --- Text Area ---
        self.text_area = scrolledtext.ScrolledText(master, wrap=tk.WORD, undo=True, state=tk.DISABLED)
        self.text_area.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)
        self.text_area.bind('<KeyRelease>', self.on_text_change)

        # --- Chat Section ---
        chat_frame = tk.LabelFrame(master, text="Real-Time Chat & Notifications")
        chat_frame.pack(padx=10, pady=5, fill='x')
        self.chat_area = scrolledtext.ScrolledText(chat_frame, wrap=tk.WORD, height=6, state=tk.DISABLED, bg='#f0f0f0')
        self.chat_area.pack(padx=5, pady=5, fill=tk.X)

        chat_input_frame = tk.Frame(chat_frame)
        chat_input_frame.pack(fill='x', padx=5, pady=5)
        self.chat_input = tk.Entry(chat_input_frame, state=tk.DISABLED)
        self.chat_input.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.chat_input.bind('<Return>', lambda event: self.send_chat())

        self.send_btn = tk.Button(chat_input_frame, text="Send", command=self.send_chat, state=tk.DISABLED)
        self.send_btn.pack(side=tk.RIGHT)

        # --- Status and Connection ---
        status_frame = tk.Frame(master)
        status_frame.pack(fill='x', padx=10)
        self.status_label = tk.Label(status_frame, text="Status: Disconnected", fg="red")
        self.status_label.pack(side=tk.LEFT)

        self.connect_button = tk.Button(status_frame, text="Connect to Server", command=self.start_socket_connection)
        self.connect_button.pack(side=tk.RIGHT)

        self.master.after(100, self.process_incoming_messages)

    # --- UI State Management ---
    def set_app_state(self, is_authenticated):
        state = tk.NORMAL if is_authenticated else tk.DISABLED
        self.text_area.config(state=state)
        self.chat_input.config(state=state)
        self.send_btn.config(state=state)
        self.save_btn.config(state=state)
        self.new_btn.config(state=state)

    def set_connection_state(self, is_connected):
        state = tk.NORMAL if is_connected else tk.DISABLED
        self.login_btn.config(state=state)
        self.signup_btn.config(state=state)

        if is_connected:
            self.connect_button.config(text="Log Out", command=self.logout)
        else:
            self.connect_button.config(text="Connect to Server", command=self.start_socket_connection)
            self.set_app_state(False)

    # --- Chat UI Helpers ---
    def append_to_chat(self, text, user="SYSTEM", color="black"):
        self.chat_area.config(state=tk.NORMAL)
        user_tag = f"user_{user}"

        if user == "SYSTEM" or user == "NOTIFICATION":
            display_color = "red" if user == "SYSTEM" else "darkorange"
        elif user not in self.user_color_map:
            color_index = hash(user) % len(self.USER_COLORS)
            self.user_color_map[user] = self.USER_COLORS[color_index]
            display_color = self.user_color_map[user]
        else:
            display_color = self.user_color_map[user]

        self.chat_area.tag_config(user_tag, foreground=display_color)

        self.chat_area.insert(tk.END, f"[{time.strftime('%H:%M:%S')}] ", "time")
        self.chat_area.insert(tk.END, f"<{user}>: ", user_tag)
        self.chat_area.insert(tk.END, f"{text}\n")

        self.chat_area.yview(tk.END)
        self.chat_area.config(state=tk.DISABLED)

    # --- Authentication Dialogs (Fixed to Appear Above) ---
    def open_signup_dialog(self):
        if not client_socket:
            mb.showerror("Error", "Connect to server first!")
            return

        # Bring window to top
        self.master.lift()
        self.master.focus_force()
        self.master.attributes("-topmost", True)
        self.master.after(200, lambda: self.master.attributes("-topmost", False))

        username = simpledialog.askstring("Sign Up", "Enter new Username:", parent=self.master)
        if not username:
            return

        password = simpledialog.askstring("Sign Up", "Enter Password:", show='*', parent=self.master)
        if not password:
            return

        self._handle_auth_request(username, password, "SIGNUP")

    def open_login_dialog_only(self):
        if not client_socket:
            mb.showerror("Error", "Socket not connected.")
            return

        # Bring window to top
        self.master.lift()
        self.master.focus_force()
        self.master.attributes("-topmost", True)
        self.master.after(200, lambda: self.master.attributes("-topmost", False))

        username = simpledialog.askstring("Login", "Enter Username:", parent=self.master)
        if not username:
            return

        password = simpledialog.askstring("Login", "Enter Password:", show='*', parent=self.master)
        if not password:
            return

        self._handle_auth_request(username, password, "LOGIN")

    def _handle_auth_request(self, username, password, type):
        global client_socket
        if client_socket:
            threading.Thread(target=self._send_credentials, args=(username, password, type)).start()
            self.status_label.config(text=f"Status: Sending {type} request...", fg="orange")

    def _send_credentials(self, username, password, type):
        global client_socket
        try:
            send_message(client_socket, {"type": type, "user": username, "password": password})
        except Exception as e:
            self.master.after(0, lambda: mb.showerror("Network Error", f"Failed to send request: {e}"))

    def logout(self):
        global GLOBAL_SESSION_ID, GLOBAL_USER_ID, client_socket

        if client_socket:
            if GLOBAL_SESSION_ID:
                send_message(client_socket, {"type": "LOGOUT", "user": GLOBAL_USER_ID, "session_id": GLOBAL_SESSION_ID})
            client_socket.close()

        GLOBAL_SESSION_ID = None
        GLOBAL_USER_ID = "UNAUTHENTICATED"
        self.status_label.config(text="Status: Disconnected", fg="red")
        self.set_connection_state(False)

    # --- File and Chat Commands ---
    def send_save_command(self):
        global GLOBAL_SESSION_ID, client_socket
        if client_socket and GLOBAL_SESSION_ID:
            send_message(client_socket, {"type": "SAVE", "session_id": GLOBAL_SESSION_ID})

    def send_new_file_command(self):
        global GLOBAL_SESSION_ID, client_socket
        if client_socket and GLOBAL_SESSION_ID:
            send_message(client_socket, {"type": "NEW_FILE", "session_id": GLOBAL_SESSION_ID})

    def send_chat(self, event=None):
        global GLOBAL_SESSION_ID, client_socket
        if client_socket and GLOBAL_SESSION_ID:
            text = self.chat_input.get()
            if text.strip():
                send_message(client_socket, {"type": "CHAT", "text": text, "session_id": GLOBAL_SESSION_ID})
                self.chat_input.delete(0, tk.END)
        return "break"

    # --- Socket Connection ---
    def start_socket_connection(self):
        if client_socket:
            self.logout()
            return

        self.status_label.config(text="Status: Connecting socket...", fg="orange")
        self.master.update()
        threading.Thread(target=self._establish_socket).start()

    def _establish_socket(self):
        global client_socket
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect((HOST, PORT))
            client_socket = sock

            send_message(client_socket, {"type": "HELLO"})
            self.master.after(0, lambda: self.status_label.config(text="Status: Socket CONNECTED. Please log in.", fg="blue"))
            self.master.after(0, self.set_connection_state, True)

            threading.Thread(target=self._listen_to_server, daemon=True).start()

        except Exception as e:
            error_msg = f"Connection Failed: {e}"
            self.master.after(0, lambda: self.status_label.config(text=error_msg, fg="red"))
            client_socket = None

    # --- Listening Thread ---
    def _listen_to_server(self):
        global client_socket
        while client_socket:
            message = recv_message(client_socket)
            if message is None:
                self.message_queue.append({"type": "DISCONNECT"})
                break
            self.message_queue.append(message)

    def process_incoming_messages(self):
        global client_socket, GLOBAL_SESSION_ID, GLOBAL_USER_ID

        while self.message_queue:
            message = self.message_queue.pop(0)
            msg_type = message.get("type")

            if msg_type == "AUTH_SUCCESS":
                if "session_id" in message:
                    GLOBAL_SESSION_ID = message.get("session_id")
                    GLOBAL_USER_ID = message.get("user")
                    self.status_label.config(text=f"Status: Authenticated as {GLOBAL_USER_ID}", fg="green")
                    self.append_to_chat("Authentication successful! Session started.", user="SYSTEM")
                    self.set_app_state(True)
                else:
                    self.append_to_chat(message.get("message", "Sign up successful!"), user="SYSTEM")

            elif msg_type == "AUTH_FAIL":
                error_msg = message.get("message", "Authentication failed.")
                mb.showerror("Authentication Error", error_msg)
                self.status_label.config(text="Status: Socket Connected (Auth Failed)", fg="blue")

            elif msg_type in ["DOC_STATE", "EDIT_UPDATE"]:
                new_content = message.get("content", "")
                current_scroll_pos = self.text_area.yview()
                current_index = self.text_area.index(tk.INSERT)
                self.text_area.delete('1.0', tk.END)
                self.text_area.insert(tk.END, new_content)
                try:
                    self.text_area.mark_set(tk.INSERT, current_index)
                except tk.TclError:
                    self.text_area.mark_set(tk.INSERT, tk.END)
                self.text_area.yview_moveto(current_scroll_pos[0])

            elif msg_type == "CHAT_MESSAGE":
                user = message.get("user")
                text = message.get("text")
                self.append_to_chat(text, user=user)

            elif msg_type == "NOTIFICATION":
                self.append_to_chat(message.get("message"), user="NOTIFICATION", color="darkorange")

            elif msg_type == "DISCONNECT":
                self.status_label.config(text="Status: Server Disconnected", fg="red")
                self.set_connection_state(False)
                client_socket = None
                GLOBAL_SESSION_ID = None
                GLOBAL_USER_ID = "UNAUTHENTICATED"

        self.master.after(100, self.process_incoming_messages)

    # --- Text Change Event ---
    def on_text_change(self, event):
        global GLOBAL_SESSION_ID, client_socket
        if client_socket and GLOBAL_SESSION_ID:
            current_content = self.text_area.get('1.0', tk.END)
            send_message(client_socket, {
                "type": "EDIT",
                "content": current_content,
                "session_id": GLOBAL_SESSION_ID
            })


# --- Main Execution ---
if __name__ == "__main__":
    root = tk.Tk()
    app = NotepadClientApp(root)
    root.mainloop()
