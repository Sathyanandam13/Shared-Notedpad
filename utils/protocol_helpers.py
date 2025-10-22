import json
import struct

def send_message(sock, message_dict):
    """Encodes and sends a JSON dictionary with a 4-byte length prefix."""
    try:
        json_data = json.dumps(message_dict).encode('utf-8')
        # Pack the length of the data into a 4-byte big-endian integer (>I)
        length_prefix = struct.pack('>I', len(json_data)) 
        sock.sendall(length_prefix + json_data)
    except Exception:
        pass # Socket error, connection is likely closed

def recv_message(sock):
    """Receives a message using the 4-byte length prefix."""
    try:
        # 1. Read the 4-byte length prefix
        raw_length = sock.recv(4)
        if not raw_length:
            return None # Connection closed

        msg_length = struct.unpack('>I', raw_length)[0]

        # 2. Read the entire message payload
        data = b''
        while len(data) < msg_length:
            chunk = sock.recv(msg_length - len(data))
            if not chunk:
                return None 
            data += chunk

        return json.loads(data.decode('utf-8'))
    except Exception:
        return None