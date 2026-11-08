"""Encrypted local outbox for SQL commands waiting on Neon."""
from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from cryptography.fernet import Fernet


class OfflineCommandQueue:
    def __init__(self, path: str | Path, key: str):
        if not key:
            raise RuntimeError("Set OFFLINE_QUEUE_KEY in .env to enable the encrypted offline command log.")
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.cipher = Fernet(key.encode())
        with self._connect() as connection:
            connection.execute("""
                CREATE TABLE IF NOT EXISTS commands (
                    command_id TEXT PRIMARY KEY,
                    payload BLOB NOT NULL,
                    status TEXT NOT NULL DEFAULT 'queued'
                        CHECK(status IN ('queued','running','applied','failed')),
                    attempts INTEGER NOT NULL DEFAULT 0,
                    last_error TEXT,
                    result TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            connection.execute("UPDATE commands SET status='queued' WHERE status='running'")
        try:
            os.chmod(self.path, 0o600)
        except OSError:
            pass

    @contextmanager
    def _connect(self):
        connection = sqlite3.connect(self.path, timeout=8, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA busy_timeout=8000")
        try:
            yield connection
        finally:
            connection.close()

    def put(self, command_id: str, payload: dict[str, Any]):
        encrypted = self.cipher.encrypt(json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode())
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as connection:
            existing = connection.execute("SELECT payload FROM commands WHERE command_id=?", (command_id,)).fetchone()
            if existing:
                saved = json.loads(self.cipher.decrypt(existing["payload"]).decode())
                if saved != payload:
                    raise ValueError("command_id was already used for a different command")
                return
            connection.execute(
                "INSERT INTO commands(command_id,payload,created_at,updated_at) VALUES(?,?,?,?)",
                (command_id, encrypted, now, now),
            )
        try:
            os.chmod(self.path, 0o600)
        except OSError:
            pass

    def get(self, command_id: str):
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM commands WHERE command_id=?", (command_id,)).fetchone()
        return self._decode(row) if row else None

    def claim(self):
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT * FROM commands WHERE status='queued' ORDER BY created_at,command_id LIMIT 1"
            ).fetchone()
            if not row:
                connection.execute("COMMIT")
                return None
            now = datetime.now(timezone.utc).isoformat()
            connection.execute(
                "UPDATE commands SET status='running',attempts=attempts+1,updated_at=? WHERE command_id=? AND status='queued'",
                (now, row["command_id"]),
            )
            connection.execute("COMMIT")
        return self._decode(row)

    def mark(self, command_id: str, status: str, *, result: dict | None = None, error: str | None = None):
        now = datetime.now(timezone.utc).isoformat()
        result_text = json.dumps(result, ensure_ascii=False, default=str) if result is not None else None
        with self._connect() as connection:
            connection.execute(
                "UPDATE commands SET status=?,last_error=?,result=COALESCE(?,result),updated_at=? WHERE command_id=?",
                (status, error[:1000] if error else None, result_text, now, command_id),
            )

    def list(self, limit: int = 100):
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM commands ORDER BY created_at DESC,command_id DESC LIMIT ?", (limit,)
            ).fetchall()
        return [self._decode(row) for row in rows]

    def _decode(self, row):
        payload = json.loads(self.cipher.decrypt(row["payload"]).decode())
        return {
            "command_id": row["command_id"],
            "payload": payload,
            "status": row["status"],
            "attempts": row["attempts"],
            "last_error": row["last_error"],
            "result": json.loads(row["result"]) if row["result"] else None,
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }
