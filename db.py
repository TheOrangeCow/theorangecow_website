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
        init_feature_requests_table(conn)


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

def init_feature_requests_table(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS feature_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            username TEXT NOT NULL,
            title TEXT NOT NULL,
            description TEXT DEFAULT '',
            status TEXT DEFAULT 'requested',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()


def create_feature_request(user_id, username, title, description):
    conn = get_db()
    conn.execute(
        "INSERT INTO feature_requests (user_id, username, title, description) VALUES (?, ?, ?, ?)",
        (user_id, username, title, description),
    )
    conn.commit()
    conn.close()


def get_all_feature_requests():
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM feature_requests ORDER BY created_at DESC"
    ).fetchall()
    conn.close()
    return rows


def get_public_roadmap():
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM feature_requests WHERE status IN ('planned', 'in_progress') ORDER BY created_at DESC"
    ).fetchall()
    conn.close()
    return rows


def update_feature_status(feature_id, status):
    conn = get_db()
    conn.execute("UPDATE feature_requests SET status = ? WHERE id = ?", (status, feature_id))
    conn.commit()
    conn.close()


def update_username(user_id, new_username):
    conn = get_db()
    conn.execute("UPDATE users SET username = ? WHERE id = ?", (new_username, user_id))
    conn.commit()
    conn.close()


def update_password(user_id, new_password_hash):
    conn = get_db()
    conn.execute("UPDATE users SET password_hash = ? WHERE id = ?", (new_password_hash, user_id))
    conn.commit()
    conn.close()