import os
import sqlite3
from contextlib import closing

DB_PATH = os.environ.get("COW_DB_PATH", os.path.join(os.path.dirname(__file__), "cow.db"))


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with closing(get_db()) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.commit()


def get_user_by_username(username):
    with closing(get_db()) as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE username = ?", (username,)
        ).fetchone()
        return dict(row) if row else None


def get_user_by_id(user_id):
    with closing(get_db()) as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return dict(row) if row else None


def create_user(username, password_hash):
    with closing(get_db()) as conn:
        cur = conn.execute(
            "INSERT INTO users (username, password_hash) VALUES (?, ?)",
            (username, password_hash),
        )
        conn.commit()
        return cur.lastrowid
