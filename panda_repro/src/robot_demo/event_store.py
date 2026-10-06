"""SQLite event store and technician feedback loop."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


SCHEMA = """
CREATE TABLE IF NOT EXISTS anomaly_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    robot_id TEXT NOT NULL,
    cycle_id TEXT NOT NULL,
    cycle_time REAL NOT NULL,
    predicted_fault TEXT NOT NULL,
    predicted_joint INTEGER NOT NULL,
    confidence REAL NOT NULL,
    sensor_summary TEXT NOT NULL,
    technician_label TEXT,
    technician_joint INTEGER,
    label_status TEXT NOT NULL DEFAULT 'unverified',
    maintenance_action TEXT,
    verified_at TEXT
);
"""


class EventStore:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(path)
        self.connection.execute(SCHEMA)
        self.connection.commit()

    def add_event(self, robot_id: str, cycle_id: str, cycle_time: float,
                  predicted_fault: str, predicted_joint: int, confidence: float,
                  sensor_summary: dict) -> int:
        cursor = self.connection.execute(
            """INSERT INTO anomaly_events
            (created_at, robot_id, cycle_id, cycle_time, predicted_fault,
             predicted_joint, confidence, sensor_summary)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (datetime.now(timezone.utc).isoformat(), robot_id, cycle_id, cycle_time,
             predicted_fault, predicted_joint, confidence, json.dumps(sensor_summary)),
        )
        self.connection.commit()
        return int(cursor.lastrowid)

    def add_feedback(self, event_id: int, label: str, joint: int,
                     action: str, status: str = "confirmed") -> None:
        if status not in {"confirmed", "rejected", "uncertain"}:
            raise ValueError("status must be confirmed, rejected, or uncertain")
        self.connection.execute(
            """UPDATE anomaly_events SET technician_label=?, technician_joint=?,
            label_status=?, maintenance_action=?, verified_at=? WHERE id=?""",
            (label, joint, status, action, datetime.now(timezone.utc).isoformat(), event_id),
        )
        self.connection.commit()

    def get_event(self, event_id: int) -> dict:
        self.connection.row_factory = sqlite3.Row
        row = self.connection.execute("SELECT * FROM anomaly_events WHERE id=?", (event_id,)).fetchone()
        return dict(row) if row else {}

    def list_events(self, confirmed_only: bool = False) -> list[dict]:
        self.connection.row_factory = sqlite3.Row
        query = "SELECT * FROM anomaly_events"
        params: tuple = ()
        if confirmed_only:
            query += " WHERE label_status='confirmed'"
        query += " ORDER BY id"
        return [dict(row) for row in self.connection.execute(query, params).fetchall()]

