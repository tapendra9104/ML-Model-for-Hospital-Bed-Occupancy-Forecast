from __future__ import annotations

import hashlib
import json
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Any

from .config import (
    APP_DB_PATH,
    DATA_DIR,
    DEFAULT_ADMIN_PASSWORD,
    DEFAULT_ADMIN_USERNAME,
    DEFAULT_ALERT_THRESHOLD,
    DEPARTMENTS,
    SESSION_TTL_HOURS,
)


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password_salt TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    token_hash TEXT NOT NULL UNIQUE,
    expires_at TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS thresholds (
    department TEXT PRIMARY KEY,
    utilization_threshold REAL NOT NULL,
    updated_by TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS alert_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    department TEXT NOT NULL,
    label TEXT NOT NULL,
    forecast_timestamp TEXT NOT NULL,
    utilization REAL NOT NULL,
    threshold REAL NOT NULL,
    severity TEXT NOT NULL,
    message TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE (department, forecast_timestamp, threshold)
);

CREATE TABLE IF NOT EXISTS scenarios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT NOT NULL,
    admissions_multiplier REAL NOT NULL,
    discharges_multiplier REAL NOT NULL,
    emergency_multiplier REAL NOT NULL,
    outbreak_delta REAL NOT NULL,
    occupancy_delta REAL NOT NULL,
    duration_hours INTEGER NOT NULL,
    created_by TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    last_run_at TEXT,
    last_run_summary TEXT
);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""


def _connect() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(APP_DB_PATH, check_same_thread=False)
    connection.row_factory = sqlite3.Row
    return connection


def _hash_password(password: str, salt: str | None = None) -> tuple[str, str]:
    password_salt = salt or secrets.token_hex(16)
    password_hash = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        bytes.fromhex(password_salt),
        240000,
    ).hex()
    return password_salt, password_hash


def _cleanup_sessions(connection: sqlite3.Connection) -> None:
    connection.execute("DELETE FROM sessions WHERE expires_at <= ?", (utcnow_iso(),))


def init_db() -> None:
    with _connect() as connection:
        connection.executescript(SCHEMA)
        _cleanup_sessions(connection)
        _ensure_default_user(connection)
        _ensure_default_thresholds(connection)
        connection.commit()


def _ensure_default_user(connection: sqlite3.Connection) -> None:
    existing = connection.execute("SELECT id FROM users WHERE username = ?", (DEFAULT_ADMIN_USERNAME,)).fetchone()
    if existing:
        return

    salt, password_hash = _hash_password(DEFAULT_ADMIN_PASSWORD)
    connection.execute(
        """
        INSERT INTO users (username, password_salt, password_hash, role, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (DEFAULT_ADMIN_USERNAME, salt, password_hash, "admin", utcnow_iso()),
    )


def _ensure_default_thresholds(connection: sqlite3.Connection) -> None:
    now = utcnow_iso()
    for department in DEPARTMENTS:
        connection.execute(
            """
            INSERT INTO thresholds (department, utilization_threshold, updated_by, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(department) DO NOTHING
            """,
            (department, DEFAULT_ALERT_THRESHOLD, DEFAULT_ADMIN_USERNAME, now),
        )


def authenticate_user(username: str, password: str) -> dict[str, Any] | None:
    with _connect() as connection:
        row = connection.execute(
            "SELECT id, username, password_salt, password_hash, role FROM users WHERE username = ?",
            (username,),
        ).fetchone()

    if not row:
        return None

    _, password_hash = _hash_password(password, row["password_salt"])
    if not secrets.compare_digest(password_hash, row["password_hash"]):
        return None

    return {
        "id": row["id"],
        "username": row["username"],
        "role": row["role"],
    }


def create_session(user_id: int) -> dict[str, Any]:
    token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    created_at = utcnow_iso()
    expires_at = (datetime.now(timezone.utc) + timedelta(hours=SESSION_TTL_HOURS)).replace(microsecond=0).isoformat()

    with _connect() as connection:
        connection.execute(
            "INSERT INTO sessions (user_id, token_hash, expires_at, created_at) VALUES (?, ?, ?, ?)",
            (user_id, token_hash, expires_at, created_at),
        )
        connection.commit()

    return {
        "token": token,
        "expires_at": expires_at,
    }


def get_user_for_token(token: str) -> dict[str, Any] | None:
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    with _connect() as connection:
        _cleanup_sessions(connection)
        row = connection.execute(
            """
            SELECT users.id, users.username, users.role
            FROM sessions
            JOIN users ON users.id = sessions.user_id
            WHERE sessions.token_hash = ? AND sessions.expires_at > ?
            """,
            (token_hash, utcnow_iso()),
        ).fetchone()
        connection.commit()

    return dict(row) if row else None


def delete_session(token: str) -> None:
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    with _connect() as connection:
        connection.execute("DELETE FROM sessions WHERE token_hash = ?", (token_hash,))
        connection.commit()


def get_thresholds() -> dict[str, float]:
    with _connect() as connection:
        rows = connection.execute(
            "SELECT department, utilization_threshold FROM thresholds ORDER BY department"
        ).fetchall()
    return {row["department"]: float(row["utilization_threshold"]) for row in rows}


def update_thresholds(thresholds: dict[str, float], updated_by: str) -> dict[str, float]:
    now = utcnow_iso()
    with _connect() as connection:
        for department, threshold in thresholds.items():
            connection.execute(
                """
                INSERT INTO thresholds (department, utilization_threshold, updated_by, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(department) DO UPDATE SET
                    utilization_threshold = excluded.utilization_threshold,
                    updated_by = excluded.updated_by,
                    updated_at = excluded.updated_at
                """,
                (department, threshold, updated_by, now),
            )
        connection.commit()
    return get_thresholds()


def record_alerts(alerts: list[dict[str, Any]]) -> None:
    if not alerts:
        return

    with _connect() as connection:
        for alert in alerts:
            connection.execute(
                """
                INSERT INTO alert_history (
                    department,
                    label,
                    forecast_timestamp,
                    utilization,
                    threshold,
                    severity,
                    message,
                    created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(department, forecast_timestamp, threshold) DO UPDATE SET
                    utilization = excluded.utilization,
                    severity = excluded.severity,
                    message = excluded.message,
                    created_at = excluded.created_at
                """,
                (
                    alert["department"],
                    alert["label"],
                    alert["timestamp"],
                    float(alert["utilization"]),
                    float(alert["threshold"]),
                    alert["severity"],
                    alert["message"],
                    utcnow_iso(),
                ),
            )
        connection.commit()


def get_alert_history(limit: int = 50) -> list[dict[str, Any]]:
    with _connect() as connection:
        rows = connection.execute(
            """
            SELECT id, department, label, forecast_timestamp, utilization, threshold, severity, message, created_at
            FROM alert_history
            ORDER BY forecast_timestamp DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [dict(row) for row in rows]


def list_scenarios() -> list[dict[str, Any]]:
    with _connect() as connection:
        rows = connection.execute(
            """
            SELECT id, name, description, admissions_multiplier, discharges_multiplier,
                   emergency_multiplier, outbreak_delta, occupancy_delta, duration_hours,
                   created_by, created_at, updated_at, last_run_at, last_run_summary
            FROM scenarios
            ORDER BY updated_at DESC, id DESC
            """
        ).fetchall()

    scenarios: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        if item["last_run_summary"]:
            item["last_run_summary"] = json.loads(item["last_run_summary"])
        scenarios.append(item)
    return scenarios


def get_scenario(scenario_id: int) -> dict[str, Any] | None:
    with _connect() as connection:
        row = connection.execute(
            """
            SELECT id, name, description, admissions_multiplier, discharges_multiplier,
                   emergency_multiplier, outbreak_delta, occupancy_delta, duration_hours,
                   created_by, created_at, updated_at, last_run_at, last_run_summary
            FROM scenarios WHERE id = ?
            """,
            (scenario_id,),
        ).fetchone()
    if not row:
        return None
    item = dict(row)
    if item["last_run_summary"]:
        item["last_run_summary"] = json.loads(item["last_run_summary"])
    return item


def upsert_scenario(payload: dict[str, Any], username: str) -> dict[str, Any]:
    now = utcnow_iso()
    with _connect() as connection:
        if payload.get("id"):
            connection.execute(
                """
                UPDATE scenarios
                SET name = ?, description = ?, admissions_multiplier = ?, discharges_multiplier = ?,
                    emergency_multiplier = ?, outbreak_delta = ?, occupancy_delta = ?, duration_hours = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    payload["name"],
                    payload.get("description", ""),
                    payload["admissions_multiplier"],
                    payload["discharges_multiplier"],
                    payload["emergency_multiplier"],
                    payload["outbreak_delta"],
                    payload["occupancy_delta"],
                    payload["duration_hours"],
                    now,
                    payload["id"],
                ),
            )
            scenario_id = int(payload["id"])
        else:
            cursor = connection.execute(
                """
                INSERT INTO scenarios (
                    name, description, admissions_multiplier, discharges_multiplier,
                    emergency_multiplier, outbreak_delta, occupancy_delta, duration_hours,
                    created_by, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    payload["name"],
                    payload.get("description", ""),
                    payload["admissions_multiplier"],
                    payload["discharges_multiplier"],
                    payload["emergency_multiplier"],
                    payload["outbreak_delta"],
                    payload["occupancy_delta"],
                    payload["duration_hours"],
                    username,
                    now,
                    now,
                ),
            )
            scenario_id = int(cursor.lastrowid)
        connection.commit()

    scenario = get_scenario(scenario_id)
    if scenario is None:
        raise ValueError("Scenario could not be saved.")
    return scenario


def delete_scenario(scenario_id: int) -> None:
    with _connect() as connection:
        connection.execute("DELETE FROM scenarios WHERE id = ?", (scenario_id,))
        connection.commit()


def update_scenario_last_run(scenario_id: int, summary: dict[str, Any]) -> None:
    with _connect() as connection:
        connection.execute(
            "UPDATE scenarios SET last_run_at = ?, last_run_summary = ?, updated_at = ? WHERE id = ?",
            (utcnow_iso(), json.dumps(summary), utcnow_iso(), scenario_id),
        )
        connection.commit()


def set_setting(key: str, value: Any) -> None:
    payload = json.dumps(value)
    with _connect() as connection:
        connection.execute(
            """
            INSERT INTO settings (key, value, updated_at) VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
            """,
            (key, payload, utcnow_iso()),
        )
        connection.commit()


def get_setting(key: str, default: Any | None = None) -> Any:
    with _connect() as connection:
        row = connection.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    if not row:
        return default
    return json.loads(row["value"])


def save_dataset_metadata(metadata: dict[str, Any]) -> None:
    set_setting("dataset_metadata", metadata)


def get_dataset_metadata() -> dict[str, Any] | None:
    return get_setting("dataset_metadata")
