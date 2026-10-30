"""Small SQLite persistence layer for DriveScope sessions and archives."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _load(value: str | None, default: Any) -> Any:
    if not value:
        return default
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return default


class SessionStore:
    def __init__(self, db_path: str | Path = "output/vehicle_agent.sqlite"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path, timeout=10)
        connection.row_factory = sqlite3.Row
        return connection

    def _init_schema(self) -> None:
        with self._connect() as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    image_ref TEXT,
                    image_path TEXT,
                    classification_json TEXT,
                    design_language_json TEXT,
                    views_json TEXT,
                    board_url TEXT
                );
                CREATE TABLE IF NOT EXISTS session_images (
                    image_ref TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    image_path TEXT NOT NULL,
                    filename TEXT,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    image_ref TEXT,
                    metadata_json TEXT,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS tool_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    call_id TEXT,
                    tool TEXT NOT NULL,
                    status TEXT NOT NULL,
                    arguments_json TEXT NOT NULL,
                    result_json TEXT NOT NULL,
                    duration_ms INTEGER NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS vehicle_archives (
                    archive_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    class_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    image_ref TEXT,
                    design_language_json TEXT NOT NULL,
                    views_json TEXT NOT NULL,
                    board_url TEXT,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id, id);
                CREATE INDEX IF NOT EXISTS idx_tool_runs_session ON tool_runs(session_id, id);
                CREATE INDEX IF NOT EXISTS idx_archives_created ON vehicle_archives(created_at DESC);
                """
            )

    def ensure_session(self, session_id: str) -> None:
        if not session_id or len(session_id) > 120:
            raise ValueError("session_id is required and must be at most 120 characters")
        now = _now()
        with self._connect() as db:
            db.execute(
                "INSERT OR IGNORE INTO sessions(session_id, created_at, updated_at) VALUES(?,?,?)",
                (session_id, now, now),
            )

    def register_image(self, session_id: str, image_ref: str, image_path: str | Path, filename: str = "") -> None:
        if not image_ref or Path(image_ref).name != image_ref or len(image_ref) > 160:
            raise ValueError("image_ref must be a safe short file reference")
        self.ensure_session(session_id)
        now = _now()
        with self._connect() as db:
            db.execute(
                "INSERT OR REPLACE INTO session_images(image_ref,session_id,image_path,filename,created_at) VALUES(?,?,?,?,?)",
                (image_ref, session_id, str(Path(image_path).resolve()), filename[:255], now),
            )
            db.execute(
                "UPDATE sessions SET image_ref=?, image_path=?, updated_at=?, "
                "classification_json=NULL, design_language_json=NULL, views_json=NULL, board_url=NULL WHERE session_id=?",
                (image_ref, str(Path(image_path).resolve()), now, session_id),
            )

    def get_image_path(self, session_id: str, image_ref: str) -> Path | None:
        with self._connect() as db:
            row = db.execute(
                "SELECT image_path FROM session_images WHERE image_ref=? AND session_id=?",
                (image_ref, session_id),
            ).fetchone()
        return Path(row["image_path"]) if row else None

    def append_message(self, session_id: str, role: str, content: str, image_ref: str | None = None, metadata: dict | None = None) -> None:
        self.ensure_session(session_id)
        now = _now()
        with self._connect() as db:
            db.execute(
                "INSERT INTO messages(session_id,role,content,image_ref,metadata_json,created_at) VALUES(?,?,?,?,?,?)",
                (session_id, role, content, image_ref, _json(metadata or {}), now),
            )
            db.execute("UPDATE sessions SET updated_at=? WHERE session_id=?", (now, session_id))

    def get_messages(self, session_id: str) -> list[dict]:
        with self._connect() as db:
            rows = db.execute("SELECT * FROM messages WHERE session_id=? ORDER BY id", (session_id,)).fetchall()
        return [
            {"role": row["role"], "content": row["content"], "image_ref": row["image_ref"], "metadata": _load(row["metadata_json"], {})}
            for row in rows
        ]

    def update_context(self, session_id: str, *, classification: dict | None = None, design_language: dict | None = None, views: list[dict] | None = None, board_url: str | None = None) -> None:
        self.ensure_session(session_id)
        fields: list[str] = ["updated_at=?"]
        values: list[Any] = [_now()]
        for column, value in (("classification_json", classification), ("design_language_json", design_language), ("views_json", views), ("board_url", board_url)):
            if value is not None:
                fields.append(f"{column}=?")
                values.append(_json(value) if column.endswith("_json") else value)
        values.append(session_id)
        with self._connect() as db:
            db.execute(f"UPDATE sessions SET {', '.join(fields)} WHERE session_id=?", values)

    def get_session(self, session_id: str) -> dict:
        self.ensure_session(session_id)
        with self._connect() as db:
            row = db.execute("SELECT * FROM sessions WHERE session_id=?", (session_id,)).fetchone()
        return {
            "session_id": session_id,
            "image_ref": row["image_ref"] if row else None,
            "classification": _load(row["classification_json"] if row else None, None),
            "design_language": _load(row["design_language_json"] if row else None, None),
            "views": _load(row["views_json"] if row else None, []),
            "board_url": row["board_url"] if row else None,
            "messages": self.get_messages(session_id),
            "tool_runs": self.list_tool_runs(session_id),
        }

    def add_tool_run(self, session_id: str, tool: str, status: str, arguments: dict, result: dict, duration_ms: int, call_id: str | None = None) -> dict:
        self.ensure_session(session_id)
        with self._connect() as db:
            cursor = db.execute(
                "INSERT INTO tool_runs(session_id,call_id,tool,status,arguments_json,result_json,duration_ms,created_at) VALUES(?,?,?,?,?,?,?,?)",
                (session_id, call_id, tool, status, _json(arguments), _json(result), max(0, int(duration_ms)), _now()),
            )
            run_id = cursor.lastrowid
        return {"id": run_id, "call_id": call_id, "tool": tool, "status": status, "arguments": arguments, "result": result, "duration_ms": max(0, int(duration_ms))}

    def list_tool_runs(self, session_id: str, limit: int = 40) -> list[dict]:
        with self._connect() as db:
            rows = db.execute("SELECT * FROM tool_runs WHERE session_id=? ORDER BY id DESC LIMIT ?", (session_id, limit)).fetchall()
        return [
            {"id": row["id"], "call_id": row["call_id"], "tool": row["tool"], "status": row["status"], "arguments": _load(row["arguments_json"], {}), "result": _load(row["result_json"], {}), "duration_ms": row["duration_ms"]}
            for row in reversed(rows)
        ]

    def save_archive(self, session_id: str, class_id: str, title: str, image_ref: str | None, design_language: dict, views: list[dict], board_url: str | None) -> dict:
        import uuid

        self.ensure_session(session_id)
        record = {"archive_id": str(uuid.uuid4()), "session_id": session_id, "class_id": class_id, "title": title[:120], "image_ref": image_ref, "design_language": design_language, "views": views, "board_url": board_url, "created_at": _now()}
        with self._connect() as db:
            db.execute(
                "INSERT INTO vehicle_archives(archive_id,session_id,class_id,title,image_ref,design_language_json,views_json,board_url,created_at) VALUES(?,?,?,?,?,?,?,?,?)",
                (record["archive_id"], session_id, class_id, record["title"], image_ref, _json(design_language), _json(views), board_url, record["created_at"]),
            )
        return record

    def search_archives(self, query: str = "", limit: int = 30) -> list[dict]:
        query = (query or "").strip()
        with self._connect() as db:
            if query:
                rows = db.execute(
                    "SELECT * FROM vehicle_archives WHERE title LIKE ? OR class_id LIKE ? ORDER BY created_at DESC LIMIT ?",
                    (f"%{query}%", f"%{query}%", limit),
                ).fetchall()
            else:
                rows = db.execute("SELECT * FROM vehicle_archives ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
        return [
            {"archive_id": row["archive_id"], "session_id": row["session_id"], "class_id": row["class_id"], "title": row["title"], "image_ref": row["image_ref"], "design_language": _load(row["design_language_json"], {}), "views": _load(row["views_json"], []), "board_url": row["board_url"], "created_at": row["created_at"]}
            for row in rows
        ]
