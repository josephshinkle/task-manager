import sqlite3
from pathlib import Path

DB_PATH = Path("/opt/render/project/data/tasks.db").resolve().parent / "tasks.db"

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def init_db():
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL    
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
                 id INTEGER PRIMARY KEY AUTOINCREMENT,
                 user_id INTEGER,
                 guest_id TEXT,
                 title TEXT NOT NULL,
                 notes TEXT,
                 completed INTEGER NOT NULL DEFAULT 0,
                 created_at TEXT NOT NULL,
                 FOREIGN KEY (user_id) REFERENCES users (id)
                 CHECK (
                    (user_id IS NOT NULL AND guest_id is NULL) OR
                    (user_id IS NULL AND guest_id IS NOT NULL)
                 )
        )
    """)
    conn.commit()
    conn.close()

def _column_exists(conn, table, column):
    cols = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return any(c["name"] == column for c in cols)

def migrate_db():
    conn = get_db_connection()
    
    # users table
    conn.execute("""
    CREATE TABLE IF NOT EXISTS user(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT NOT NULL UNIQUE,           
        password_hash TEXT NOT NULL,
        created_at TEXT NOT NULL                                    
    )
    """)

    # Add user_id column (if tasks already existed before user_id)
    if not _column_exists(conn, "tasks", "user_id"):
        conn.execute("ALTER TABLE tasks ADD COLUMN user_id INTEGER")

    # Add guest_id cloumn to taks if missing
    if not _column_exists(conn, "tasks", "guest_id"):
        conn.execute("ALTER TABLE tasks ADD COLUMN guest_id TEXT")
    
    conn.commit()
    conn.close()