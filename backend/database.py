import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Iterator
from uuid import uuid4

from .config import DATABASE_PATH, DATA_DIR


def initialize_database() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with connect() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS analyses (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                created_at TEXT NOT NULL,
                overall_score INTEGER NOT NULL,
                skin_type TEXT NOT NULL,
                confidence INTEGER NOT NULL,
                result_json TEXT NOT NULL
            )
            """
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_analyses_session_created "
            "ON analyses(session_id, created_at DESC)"
        )


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    try:
        yield connection
        connection.commit()
    finally:
        connection.close()


def save_analysis(session_id: str, result: dict[str, Any]) -> tuple[str, str]:
    analysis_id = str(uuid4())
    created_at = datetime.now(timezone.utc).isoformat()
    with connect() as connection:
        connection.execute(
            """
            INSERT INTO analyses
                (id, session_id, created_at, overall_score, skin_type, confidence, result_json)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                analysis_id,
                session_id,
                created_at,
                result["overall"],
                result["skinType"],
                result["confidence"],
                json.dumps(result, ensure_ascii=False, separators=(",", ":")),
            ),
        )
    return analysis_id, created_at


def list_analyses(session_id: str, limit: int = 20) -> list[dict[str, Any]]:
    with connect() as connection:
        rows = connection.execute(
            """
            SELECT id, created_at, overall_score, skin_type, confidence, result_json
            FROM analyses
            WHERE session_id = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (session_id, limit),
        ).fetchall()
    return [
        {
            "id": row["id"],
            "createdAt": row["created_at"],
            "overall": row["overall_score"],
            "skinType": row["skin_type"],
            "confidence": row["confidence"],
            "result": json.loads(row["result_json"]),
        }
        for row in rows
    ]


def delete_analysis(session_id: str, analysis_id: str) -> bool:
    with connect() as connection:
        cursor = connection.execute(
            "DELETE FROM analyses WHERE id = ? AND session_id = ?",
            (analysis_id, session_id),
        )
    return cursor.rowcount > 0


def delete_session_history(session_id: str) -> int:
    with connect() as connection:
        cursor = connection.execute(
            "DELETE FROM analyses WHERE session_id = ?",
            (session_id,),
        )
    return cursor.rowcount
