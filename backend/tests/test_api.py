import os
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

TEST_DIR = Path(tempfile.mkdtemp(prefix="hospital-bed-tests-"))
os.environ["HOSPITAL_APP_DB_PATH"] = str(TEST_DIR / "hospital_app.sqlite3")
os.environ["HOSPITAL_ACTIVITY_DATA_PATH"] = str(TEST_DIR / "hospital_activity.csv")
os.environ["HOSPITAL_HIS_RAW_DATA_PATH"] = str(TEST_DIR / "his_source.csv")

from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.persistence import init_db

init_db()
client = TestClient(app)


def auth_headers() -> dict[str, str]:
    response = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "admin123"},
    )
    assert response.status_code == 200
    token = response.json()["token"]
    return {"Authorization": f"Bearer {token}"}


def build_event_level_csv() -> str:
    rows = ["patient_id,admission_time,discharge_time,department,admission_type"]
    start = datetime(2026, 1, 1, 0, 0)
    departments = [
        "ICU",
        "General Ward",
        "Emergency Department",
        "Pediatric Ward",
        "General Ward",
        "ICU",
    ]
    for index in range(220):
        admission = start + timedelta(hours=index * 2)
        discharge = admission + timedelta(hours=18 + (index % 30))
        department = departments[index % len(departments)]
        admission_type = "Emergency" if "Emergency" in department or index % 5 == 0 else "Scheduled"
        rows.append(
            f"P{index},{admission.isoformat()},{discharge.isoformat()},{department},{admission_type}"
        )
    return "\n".join(rows)


def test_dashboard_requires_authentication() -> None:
    response = client.get("/api/dashboard")
    assert response.status_code == 401


def test_login_dashboard_and_threshold_update() -> None:
    headers = auth_headers()

    dashboard_response = client.get("/api/dashboard?horizon_hours=24", headers=headers)
    assert dashboard_response.status_code == 200
    dashboard = dashboard_response.json()
    assert {"overview", "forecasts", "alerts", "trends", "thresholds", "dataset"} <= set(dashboard.keys())

    threshold_response = client.put(
        "/api/admin/thresholds",
        headers=headers,
        json={"thresholds": {"icu": 0.88, "ward": 0.91, "emergency": 0.9, "pediatric": 0.87}},
    )
    assert threshold_response.status_code == 200
    assert threshold_response.json()["icu"] == 0.88


def test_ingest_real_his_data_and_simulate_scenario() -> None:
    headers = auth_headers()
    csv_text = build_event_level_csv()

    ingest_response = client.post(
        "/api/admin/datasets/ingest",
        headers=headers,
        json={"dataset_name": "Hospital HIS Export", "csv_text": csv_text},
    )
    assert ingest_response.status_code == 200
    dataset = ingest_response.json()["dataset"]
    assert dataset["source_type"] == "event_level_his"

    scenario_response = client.post(
        "/api/admin/scenarios",
        headers=headers,
        json={
            "name": "Influenza surge",
            "description": "Simulate increased emergency inflow and outbreak pressure.",
            "admissions_multiplier": 1.15,
            "discharges_multiplier": 0.95,
            "emergency_multiplier": 1.25,
            "outbreak_delta": 0.2,
            "occupancy_delta": 4,
            "duration_hours": 72,
        },
    )
    assert scenario_response.status_code == 200
    scenario_id = scenario_response.json()["id"]

    simulation_response = client.post(
        f"/api/admin/scenarios/{scenario_id}/simulate?horizon_hours=48",
        headers=headers,
    )
    assert simulation_response.status_code == 200
    simulation = simulation_response.json()
    assert len(simulation["forecasts"]) == 4
    assert len(simulation["summary"]) == 4
