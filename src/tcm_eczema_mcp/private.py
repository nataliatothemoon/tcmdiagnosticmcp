"""Private follow-up list. Name and email never go into the knowledge-base case files."""

from __future__ import annotations

import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS case_links (
    case_number TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL
);
"""


class PrivateRegistry:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as conn:
            conn.executescript(SCHEMA)

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def add_mailing_contact(self, name: str, email: str) -> int:
        cleaned_name = clean_name(name)
        cleaned_email = clean_email(email)
        now = datetime.now(timezone.utc).isoformat()
        with self.connect() as conn:
            row = conn.execute("SELECT id FROM users WHERE email = ?", (cleaned_email,)).fetchone()
            if row is None:
                cursor = conn.execute(
                    "INSERT INTO users (name, email, created_at) VALUES (?, ?, ?)",
                    (cleaned_name, cleaned_email, now),
                )
                return int(cursor.lastrowid)
            conn.execute("UPDATE users SET name = ? WHERE id = ?", (cleaned_name, row["id"]))
            return int(row["id"])

    def link_case(self, case_number: str, name: str, email: str) -> None:
        user_id = self.add_mailing_contact(name, email)
        now = datetime.now(timezone.utc).isoformat()
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO case_links (case_number, user_id, created_at)
                VALUES (?, ?, ?)
                """,
                (case_number, user_id, now),
            )

    def follow_up(self, case_number: str) -> dict | None:
        with self.connect() as conn:
            row = conn.execute(
                """
                SELECT case_links.case_number, users.name, users.email
                FROM case_links
                JOIN users ON users.id = case_links.user_id
                WHERE case_links.case_number = ?
                """,
                (case_number,),
            ).fetchone()
        return dict(row) if row else None

    def mailing_list(self) -> list[dict]:
        with self.connect() as conn:
            rows = conn.execute("SELECT name, email FROM users ORDER BY email").fetchall()
        return [dict(row) for row in rows]


def clean_name(name: str) -> str:
    cleaned = " ".join(name.split())
    if not cleaned:
        raise ValueError("A name is required for the private follow-up list.")
    if len(cleaned) > 200:
        raise ValueError("Name must be 200 characters or fewer.")
    return cleaned


def clean_email(email: str) -> str:
    cleaned = email.strip().lower()
    if EMAIL_RE.fullmatch(cleaned) is None:
        raise ValueError("Email must look like a name and a domain, such as name@example.com.")
    return cleaned
