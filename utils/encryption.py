# utils/encryption.py (FINAL FIXED VERSION for PostgreSQL compatibility)
import bcrypt

def hash_password(password):
    """Hashes a plaintext password using bcrypt."""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())


def check_password(password, stored_hashed_password):
    """
    Verifies a plaintext password against a stored bcrypt hash.
    Handles BYTEA (memoryview) type returned from psycopg2.
    """
    try:
        # 1️⃣ Convert password to bytes
        password_bytes = password.encode('utf-8')

        # 2️⃣ Handle all possible psycopg2 data return types
        if isinstance(stored_hashed_password, memoryview):
            stored_hashed_password = stored_hashed_password.tobytes()
        elif isinstance(stored_hashed_password, str):
            stored_hashed_password = stored_hashed_password.encode('utf-8')
        elif not isinstance(stored_hashed_password, bytes):
            stored_hashed_password = bytes(stored_hashed_password)

        # 3️⃣ Verify password using bcrypt
        return bcrypt.checkpw(password_bytes, stored_hashed_password)

    except Exception as e:
        print(f"[Encryption Error] Password verification failed: {e}")
        return False


# --- Optional Local Test Block ---
if __name__ == "__main__":
    pwd = "test123"
    hashed = hash_password(pwd)
    print("Generated Hash:", hashed)
    print("Check Correct:", check_password("test123", hashed))
    print("Check Wrong:", check_password("wrongpass", hashed))
