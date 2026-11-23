"""SQLite persistence for detection records."""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone

from .config import DB_PATH


@contextmanager
def _connect():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS detections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                original_filename TEXT NOT NULL,
                image_filename TEXT NOT NULL,
                result TEXT NOT NULL,
                confidence REAL NOT NULL,
                denomination TEXT,
                model_mode TEXT NOT NULL DEFAULT 'demo',
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_detections_created "
            "ON detections(created_at DESC)"
        )


def _serialize(row: sqlite3.Row) -> dict:
    item = dict(row)
    item["image_url"] = f"/uploads/{item['image_filename']}"
    item["report_url"] = f"/api/detections/{item['id']}/report"
    return item


def insert_detection(
    *,
    original_filename: str,
    image_filename: str,
    result: str,
    confidence: float,
    denomination: str | None,
    model_mode: str,
    created_at: str | None = None,
) -> dict:
    timestamp = created_at or datetime.now(timezone.utc).isoformat(timespec="seconds")
    with _connect() as conn:
        cursor = conn.execute(
            """
            INSERT INTO detections
                (original_filename, image_filename, result, confidence,
                 denomination, model_mode, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                original_filename,
                image_filename,
                result,
                confidence,
                denomination,
                model_mode,
                timestamp,
            ),
        )
        row = conn.execute(
            "SELECT * FROM detections WHERE id = ?", (cursor.lastrowid,)
        ).fetchone()
    return _serialize(row)


def list_detections(
    result: str | None = None, limit: int = 20, offset: int = 0
) -> tuple[list[dict], int]:
    where = ""
    params: list = []
    if result in {"REAL", "FAKE"}:
        where = "WHERE result = ?"
        params.append(result)

    with _connect() as conn:
        total = conn.execute(
            f"SELECT COUNT(*) FROM detections {where}", params
        ).fetchone()[0]
        rows = conn.execute(
            f"SELECT * FROM detections {where} "
            "ORDER BY created_at DESC, id DESC LIMIT ? OFFSET ?",
            [*params, limit, offset],
        ).fetchall()
    return [_serialize(row) for row in rows], int(total)


def get_detection(detection_id: int) -> dict | None:
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM detections WHERE id = ?", (detection_id,)
        ).fetchone()
    return _serialize(row) if row else None


def delete_detection(detection_id: int) -> dict | None:
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM detections WHERE id = ?", (detection_id,)
        ).fetchone()
        if row is None:
            return None
        conn.execute("DELETE FROM detections WHERE id = ?", (detection_id,))
    return _serialize(row)


def get_stats() -> dict:
    with _connect() as conn:
        row = conn.execute(
            """
            SELECT
                COUNT(*) AS total,
                COALESCE(SUM(result = 'FAKE'), 0) AS fake,
                COALESCE(SUM(result = 'REAL'), 0) AS real,
                COALESCE(AVG(confidence), 0) AS avg_confidence
            FROM detections
            """
        ).fetchone()
    data = dict(row)
    data["avg_confidence"] = round(float(data["avg_confidence"]), 4)
    return data
