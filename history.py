import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).parent / "history.db"


def filter_clips(items, query):
    """Case-insensitive substring filter over clip dicts (the popup's search box).
    A blank/whitespace-only query returns everything, unchanged and in order."""
    query = (query or "").lower().strip()
    if not query:
        return list(items)
    return [it for it in items if query in it["text"].lower()]


class History:
    def __init__(self, db_path=DB_PATH, max_entries=500):
        self.db_path = db_path
        self.max_entries = max_entries
        self._lock = threading.Lock()
        # One connection reused for the app's lifetime (add/recent/clear are all
        # called from different threads, but every access goes through _lock,
        # so check_same_thread=False is safe here).
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._init_db()

    def _init_db(self):
        with self._lock:
            self._conn.execute(
                """CREATE TABLE IF NOT EXISTS clips (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    text TEXT NOT NULL UNIQUE,
                    updated_at TEXT NOT NULL
                )"""
            )
            self._conn.commit()

    def add(self, text):
        if not text or not text.strip():
            return
        now = datetime.now(timezone.utc).isoformat()
        with self._lock:
            self._conn.execute(
                """INSERT INTO clips (text, updated_at) VALUES (?, ?)
                   ON CONFLICT(text) DO UPDATE SET updated_at=excluded.updated_at""",
                (text, now),
            )
            # Cap history: keep only the most recent max_entries rows.
            self._conn.execute(
                """DELETE FROM clips WHERE id IN (
                       SELECT id FROM clips ORDER BY updated_at DESC
                       LIMIT -1 OFFSET ?
                   )""",
                (self.max_entries,),
            )
            self._conn.commit()

    def recent(self, limit=200):
        with self._lock:
            cur = self._conn.execute(
                "SELECT text, updated_at FROM clips ORDER BY updated_at DESC LIMIT ?", (limit,)
            )
            return [{"text": row[0], "updated_at": row[1]} for row in cur.fetchall()]

    def count(self):
        with self._lock:
            cur = self._conn.execute("SELECT COUNT(*) FROM clips")
            return cur.fetchone()[0]

    def clear(self):
        with self._lock:
            self._conn.execute("DELETE FROM clips")
            self._conn.commit()
