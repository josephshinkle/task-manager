import sqlite3

DB_PATH = "tasks.db"

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