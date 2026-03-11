from __future__ import annotations

import math
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "backend" / "data"
DATA_PATH = Path(os.getenv("HOSPITAL_ACTIVITY_DATA_PATH", str(DATA_DIR / "hospital_activity.csv")))
RAW_HIS_DATA_PATH = Path(os.getenv("HOSPITAL_HIS_RAW_DATA_PATH", str(DATA_DIR / "his_source.csv")))
APP_DB_PATH = Path(os.getenv("HOSPITAL_APP_DB_PATH", str(DATA_DIR / "hospital_app.sqlite3")))

DEFAULT_CAPACITIES = {
    "icu": 48,
    "ward": 260,
    "emergency": 72,
    "pediatric": 45,
}

DEPARTMENT_LABELS = {
    "icu": "ICU",
    "ward": "General Ward",
    "emergency": "Emergency",
    "pediatric": "Pediatric",
}

DEPARTMENTS = tuple(DEFAULT_CAPACITIES.keys())
FORECAST_LIMIT_HOURS = 24 * 7
DEFAULT_FORECAST_HOURS = 48
DEFAULT_ALERT_THRESHOLD = 0.9
SESSION_TTL_HOURS = 12
DEFAULT_ADMIN_USERNAME = os.getenv("HOSPITAL_ADMIN_USERNAME", "admin")
DEFAULT_ADMIN_PASSWORD = os.getenv("HOSPITAL_ADMIN_PASSWORD", "admin123")
MIN_TRAINING_ROWS = 120


def occupancy_column(department: str) -> str:
    return f"{department}_occupied"


def round_capacity(value: float) -> int:
    rounded = max(5, int(math.ceil(value / 5.0) * 5))
    return rounded
