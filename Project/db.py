import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "tasks.db"

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
                 id INTEGER PRIMARY KEY AUTOINCREMENT,
                 title TEXT NOT NULL,
                 notes TEXT,
                 completed INTEGER NOT NULL DEFAULT 0,
                 created_at TEXT NOT NULL
        );
    """)
    conn.commit()
    conn.close()

def _column_exists(conn, table, column):
    cols = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return any(c["name"] == column for c in cols)

def migrate_db():
    conn = get_db_connection()
    
    #1 users table
    conn.execute("""
    CREATE TABLE IF NOT EXISTS user(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL UNIQUE,           
    password_hash TEXT NOT NULL,
    created_at TEXT NOT NULL                                    
    )
    """)

    #2 tasks.user_id column (if tasks already existed before user_id)
    if not _column_exists(conn, "tasks", "user_id"):
        conn.execute("ALTER TABLE tasks ADD COLUMN user_id INTEGER")
    
    conn.commit()
    conn.close()