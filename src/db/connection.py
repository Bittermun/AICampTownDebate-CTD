# TASK-002 output - see CODEX_QUEUE.md
import os
import sqlite3
from pathlib import Path

DB_URL = os.getenv("DB_URL", "sqlite:///data/league.db")


def get_db():
    if DB_URL.startswith("sqlite"):
        path = DB_URL.split("///")[1]
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        schema = Path(__file__).parent / "schema_sqlite.sql"
        conn.executescript(schema.read_text())
        return conn
    else:
        import psycopg2
        import psycopg2.extras

        conn = psycopg2.connect(DB_URL)
        conn.cursor_factory = psycopg2.extras.RealDictCursor
        return conn
