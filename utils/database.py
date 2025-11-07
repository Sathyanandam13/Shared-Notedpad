# utils/database.py
import psycopg2
from psycopg2 import pool
from psycopg2 import errors
from utils.encryption import hash_password

# --- PostgreSQL Connection Configuration (UPDATE THIS!) ---
DB_CONFIG = {
    'user': 'postgres',
    'password': 'nandam100', 
    'host': 'localhost',
    'port': '5432',
    'database': 'notepad_db' # Ensure this database exists
}

db_pool = None

def initialize_db():
    """Initializes the PostgreSQL connection pool and creates the users table."""
    global db_pool
    try:
        db_pool = pool.SimpleConnectionPool(1, 20, **DB_CONFIG)
        print("Database connection pool established successfully.")
        
        conn = db_pool.getconn()
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                username VARCHAR(50) UNIQUE NOT NULL,
                password_hash BYTEA NOT NULL,
                is_admin BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        conn.commit()
        cursor.close()
        db_pool.putconn(conn)
        print("Users table checked/created.")

    except psycopg2.Error as e:
        print(f"Database Initialization Error: {e}")
        # If the server cannot connect to PostgreSQL, the application will fail here.

def create_user(username, password, is_admin=False):
    """Inserts a new user (SIGNUP) into the database."""
    conn = db_pool.getconn()
    cursor = conn.cursor()
    try:
        hashed_password = hash_password(password)
        cursor.execute(
            "INSERT INTO users (username, password_hash, is_admin) VALUES (%s, %s, %s) RETURNING id;",
            (username, hashed_password, is_admin)
        )
        conn.commit()
        user_id = cursor.fetchone()[0]
        return user_id
    except errors.UniqueViolation:
        conn.rollback()
        return None
    except psycopg2.Error as e:
        print(f"Error creating user: {e}")
        conn.rollback()
        return None
    finally:
        cursor.close()
        db_pool.putconn(conn)

def find_user_by_username(username):
    """Retrieves user data and the hashed password for login."""
    conn = db_pool.getconn()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT id, username, password_hash, is_admin FROM users WHERE username = %s;",
            (username,)
        )
        user_data = cursor.fetchone()
        if user_data:
            return {
                'id': user_data[0],
                'username': user_data[1],
                'password_hash': user_data[2],
                'is_admin': user_data[3]
            }
        return None
    finally:
        cursor.close()
        db_pool.putconn(conn)