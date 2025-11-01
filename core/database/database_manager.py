import sqlite3
import threading
import os
import logging
from datetime import datetime, timezone, timedelta
import json

logger = logging.getLogger(__name__)

import pathlib
# Directory for all bot databases
MAIN_ROOT = pathlib.Path(__file__).resolve().parents[2]
DB_DIR = os.path.join(MAIN_ROOT, "databases")
os.makedirs(DB_DIR, exist_ok=True)


class DatabaseManager:
    def mark_scheduled_as_sent(self, msg_id: int):
        """Mark a scheduled message as sent."""
        with self.lock, self._connect() as conn:
            c = conn.cursor()
            c.execute("UPDATE scheduled_messages SET sent = 1 WHERE id = ?", (msg_id,))
            conn.commit()
    def get_pending_scheduled_messages(self):
        """Return all scheduled messages that are not sent yet."""
        with self.lock, self._connect() as conn:
            c = conn.cursor()
            c.execute("SELECT * FROM scheduled_messages WHERE sent = 0 ORDER BY send_time ASC")
            rows = c.fetchall()
            return [dict(row) for row in rows]
    """
    Thread-safe SQLite database handler for Telegram bot persistence.
    Automatically creates the schema on initialization and provides
    helper methods for user, admin, message, and scheduling management.
    """

    def __init__(self, bot_id: int | str):
        self.db_path = os.path.join(DB_DIR, f"bot_{bot_id}.db")
        self.lock = threading.Lock()
        self._initialize_database()
        logger.info(f"📦 Database initialized at {self.db_path}")

    # -------------------------------------------------------------------------
    # Initialization and Connection
    # -------------------------------------------------------------------------
    def _connect(self):
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _initialize_database(self):
        """Create tables if not already existing."""
        with self._connect() as conn:
            c = conn.cursor()

            # Users table
            c.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_id INTEGER UNIQUE,
                    username TEXT,
                    chat_type TEXT,
                    first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Roles table (for admins, moderators, superadmins, etc.)
            c.execute("""
                CREATE TABLE IF NOT EXISTS roles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER UNIQUE,
                    role TEXT DEFAULT 'user',
                    added_on TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Messages table (for chat logging or future LLM memory)
            # c.execute("""
            #     CREATE TABLE IF NOT EXISTS messages (
            #         id INTEGER PRIMARY KEY AUTOINCREMENT,
            #         chat_id INTEGER,
            #         user_id INTEGER,
            #         text TEXT,
            #         timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            #     )
            # """)

            # Settings table
            c.execute("""
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            """)

            # Blocked users table
            c.execute("""
                CREATE TABLE IF NOT EXISTS blocked_users (
                    chat_id INTEGER PRIMARY KEY,
                    blocked INTEGER DEFAULT 1,
                    updated_on TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Scheduled messages
            c.execute("""
                CREATE TABLE IF NOT EXISTS scheduled_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    target_type TEXT,     -- 'individuals', 'groups', 'all'
                    message TEXT,
                    send_time TIMESTAMP,
                    sent INTEGER DEFAULT 0
                )
            """)

            conn.commit()

    # -------------------------------------------------------------------------
    # Users
    # -------------------------------------------------------------------------
    def add_user(self, chat_id: int, username: str | None, chat_type: str):
        with self.lock, self._connect() as conn:
            c = conn.cursor()
            c.execute("""
                INSERT OR IGNORE INTO users (chat_id, username, chat_type)
                VALUES (?, ?, ?)
            """, (chat_id, username, chat_type))
            conn.commit()

    def ensure_user_exists(self, user_id: int, username: str | None = None, chat_type: str = "private"):
        self.add_user(user_id, username or "", chat_type)

    def ensure_chat_exists(self, chat_id: int, chat_type: str):
        self.add_user(chat_id, None, chat_type)

    def get_all_chats(self):
        with self.lock, self._connect() as conn:
            c = conn.cursor()
            c.execute("SELECT chat_id, chat_type FROM users")
            return [dict(row) for row in c.fetchall()]

    def get_chats_by_type(self, target: str):
        """Map admin target types to chat_type values."""
        with self.lock, self._connect() as conn:
            c = conn.cursor()
            if target == "individuals":
                c.execute("SELECT chat_id FROM users WHERE chat_type = 'private'")
            elif target == "groups":
                c.execute("SELECT chat_id FROM users WHERE chat_type IN ('group','supergroup')")
            elif target == "all":
                c.execute("SELECT chat_id FROM users")
            else:
                return []
            return [row["chat_id"] for row in c.fetchall()]

    def count_users(self):
        with self.lock, self._connect() as conn:
            c = conn.cursor()
            c.execute("SELECT COUNT(*) AS cnt FROM users")
            return c.fetchone()["cnt"]

    # -------------------------------------------------------------------------
    # Roles (Admin / Moderator / SuperAdmin)
    # -------------------------------------------------------------------------
    def add_role(self, user_id: int, role: str):
        with self.lock, self._connect() as conn:
            c = conn.cursor()
            if role not in ("admin", "superadmin"):
                # Drop user from roles table if not admin/superadmin
                c.execute("DELETE FROM roles WHERE user_id = ?", (user_id,))
            else:
                c.execute("""
                    INSERT OR REPLACE INTO roles (user_id, role)
                    VALUES (?, ?)
                """, (user_id, role))
            conn.commit()

    def get_roles(self):
        with self.lock, self._connect() as conn:
            c = conn.cursor()
            c.execute("SELECT user_id, role FROM roles")
            return [dict(row) for row in c.fetchall()]

    def get_users_by_role(self, role: str):
        with self.lock, self._connect() as conn:
            c = conn.cursor()
            c.execute("SELECT user_id FROM roles WHERE role = ?", (role,))
            return [row["user_id"] for row in c.fetchall()]

    def is_role(self, user_id: int, role: str):
        with self.lock, self._connect() as conn:
            c = conn.cursor()
            c.execute("SELECT 1 FROM roles WHERE user_id = ? AND role = ?", (user_id, role))
            return c.fetchone() is not None

    # -------------------------------------------------------------------------
    # Messages
    # -------------------------------------------------------------------------
    def save_message(self, chat_id: int, user_id: int, text: str):
        """
        Save a message to the messages table. Creates the table if it does not exist.
        """
        with self.lock, self._connect() as conn:
            c = conn.cursor()
            # Ensure messages table exists
            c.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_id INTEGER,
                    user_id INTEGER,
                    text TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            c.execute(
                "INSERT INTO messages (chat_id, user_id, text, timestamp) VALUES (?, ?, ?, ?)",
                (chat_id, user_id, text, datetime.now(timezone.utc))
            )
            conn.commit()
    # ─────────────────────────────────────────────
    # Developer Utility Functions
    # ─────────────────────────────────────────────
    def create_table(self, table_name: str, columns: dict):
        """
        Create a new table with robust column definitions.
        columns: dict of column_name -> dict(type, primary, foreign, allow_null, etc)
        Example:
            columns = {
                "id": {"type": "INTEGER", "primary": True},
                "name": {"type": "TEXT", "allow_null": False},
                "ref_id": {"type": "INTEGER", "foreign": ("other_table", "id")}
            }
        """
        col_defs = []
        foreign_keys = []
        # Ensure created_at column is present
        columns_with_created = dict(columns)
        if "created_at" not in columns_with_created:
            columns_with_created["created_at"] = {"type": "TIMESTAMP", "allow_null": False}
        for col, opts in columns_with_created.items():
            col_type = opts.get("type", "TEXT")
            allow_null = "NULL" if opts.get("allow_null", True) else "NOT NULL"
            col_def = f"{col} {col_type} {allow_null}"
            if opts.get("primary", False):
                col_def += " PRIMARY KEY"
            if opts.get("foreign"):
                ref_table, ref_col = opts["foreign"]
                foreign_keys.append(f"FOREIGN KEY({col}) REFERENCES {ref_table}({ref_col})")
            col_defs.append(col_def)
        if foreign_keys:
            col_defs += foreign_keys
        col_defs_str = ", ".join(col_defs)
        sql = f"CREATE TABLE IF NOT EXISTS {table_name} ({col_defs_str})"
        with self.lock, self._connect() as conn:
            c = conn.cursor()
            c.execute(sql)
            conn.commit()

    def add_entry(self, table_name: str, attributes: dict):
        table_cols = [col['name'] for col in self.get_table_columns(table_name)]
        attrs = dict(attributes)

        if "created_at" in table_cols and "created_at" not in attrs:
            tz_name = self.get_setting("timezone") or "UTC"

            try:
                import pytz
                tz = pytz.timezone(tz_name)
            except Exception:
                tz = timezone.utc
            now = datetime.now(tz)
            tz_str = now.strftime("%z")
            if tz_str.endswith("00"):
                tz_str = tz_str[:-2]
            attrs["created_at"] = now.strftime("%Y-%m-%d %H:%M ") + tz_str

        cols = ", ".join(attrs.keys())
        placeholders = ", ".join(["?" for _ in attrs])
        sql = f"INSERT INTO {table_name} ({cols}) VALUES ({placeholders})"

        with self.lock, self._connect() as conn:
            c = conn.cursor()
            c.execute(sql, tuple(attrs.values()))
            conn.commit()


    def delete_row(self, table_name: str, pk_col: str, pk_value):
        """
        Delete a row using primary key and table name.
        """
        sql = f"DELETE FROM {table_name} WHERE {pk_col} = ?"
        with self.lock, self._connect() as conn:
            c = conn.cursor()
            c.execute(sql, (pk_value,))
            conn.commit()

    def delete_table(self, table_name: str):
        """
        Delete an entire table.
        """
        sql = f"DROP TABLE IF EXISTS {table_name}"
        with self.lock, self._connect() as conn:
            c = conn.cursor()
            c.execute(sql)
            conn.commit()

    def get_table_columns(self, table_name: str):
        """
        Get column info for a table.
        """
        with self.lock, self._connect() as conn:
            c = conn.cursor()
            c.execute(f"PRAGMA table_info({table_name})")
            return [dict(row) for row in c.fetchall()]

    def get_all_rows(self, table_name: str):
        """
        Get all rows from a table.
        """
        with self.lock, self._connect() as conn:
            c = conn.cursor()
            c.execute(f"SELECT * FROM {table_name}")
            return [dict(row) for row in c.fetchall()]

    # -------------------------------------------------------------------------
    # Scheduled Messages
    # -------------------------------------------------------------------------
    def add_scheduled_message(self, target_type: str, message: str, send_time: datetime):
        with self.lock, self._connect() as conn:
            c = conn.cursor()
            c.execute("""
                INSERT INTO scheduled_messages (target_type, message, send_time)
                VALUES (?, ?, ?)
            """, (target_type, message, send_time))
            conn.commit()

    def get_due_scheduled_messages(self, now: datetime):
        with self.lock, self._connect() as conn:
            c = conn.cursor()
            c.execute("""
                SELECT * FROM scheduled_messages
                WHERE sent = 0 AND send_time <= ?
            """, (now,))
            return [
                {"id": r["id"], "target": r["target_type"], "text": r["message"], "send_time": r["send_time"]}
                for r in c.fetchall()
            ]

    def mark_scheduled_sent(self, msg_id: int):
        with self.lock, self._connect() as conn:
            c = conn.cursor()
            c.execute("UPDATE scheduled_messages SET sent = 1 WHERE id = ?", (msg_id,))
            conn.commit()

    # -------------------------------------------------------------------------
    # Settings
    # -------------------------------------------------------------------------
    def set_setting(self, key: str, value):
        with self.lock, self._connect() as conn:
            c = conn.cursor()
            c.execute(
                "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                (key, json.dumps(value))
            )
            conn.commit()

    def get_setting(self, key: str):
        with self.lock, self._connect() as conn:
            c = conn.cursor()
            c.execute("SELECT value FROM settings WHERE key = ?", (key,))
            row = c.fetchone()
            if not row:
                return None
            try:
                return json.loads(row["value"])
            except Exception:
                return row["value"]

    def get_all_settings(self):
        with self.lock, self._connect() as conn:
            c = conn.cursor()
            c.execute("SELECT key, value FROM settings")
            settings = {}
            for r in c.fetchall():
                try:
                    settings[r["key"]] = json.loads(r["value"])
                except Exception:
                    settings[r["key"]] = r["value"]
            return settings

    # -------------------------------------------------------------------------
    # Blocked Users
    # -------------------------------------------------------------------------
    def set_user_blocked(self, chat_id: int, blocked: bool = True):
        with self.lock, self._connect() as conn:
            c = conn.cursor()
            c.execute("""
                INSERT OR REPLACE INTO blocked_users (chat_id, blocked, updated_on)
                VALUES (?, ?, CURRENT_TIMESTAMP)
            """, (chat_id, 1 if blocked else 0))
            conn.commit()

    def is_user_blocked(self, chat_id: int) -> bool:
        """Check if a user is currently blocked."""
        with self.lock, self._connect() as conn:
            c = conn.cursor()
            c.execute("SELECT blocked FROM blocked_users WHERE chat_id = ?", (chat_id,))
            row = c.fetchone()
            return bool(row and row['blocked'])
