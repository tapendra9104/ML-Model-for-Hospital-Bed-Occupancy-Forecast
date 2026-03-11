from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware

from .auth import bearer_scheme, require_admin, require_auth
from .config import DEFAULT_FORECAST_HOURS
from .data_loader import normalize_his_dataset, save_training_dataset
from .persistence import (
    authenticate_user,
    create_session,
    delete_session,
    get_alert_history,
    get_scenario,
    get_thresholds,
    init_db,
    list_scenarios,
    save_dataset_metadata,
    update_scenario_last_run,
    update_thresholds,
    upsert_scenario,
)
from .schemas import CsvIngestionRequest, LoginRequest, ScenarioPayload, ThresholdUpdateRequest
from .services import get_forecast_service, reset_forecast_service


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    get_forecast_service()
    yield


app = FastAPI(
    title="Hospital Bed Occupancy Forecasting API",
    version="0.2.0",
    description="Forecasting, authentication, and scenario modeling API for hospital bed occupancy.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/auth/login")
def login(payload: LoginRequest) -> dict[str, object]:
    user = authenticate_user(payload.username, payload.password)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials.")

    session = create_session(int(user["id"]))
    return {
        "token": session["token"],
        "expires_at": session["expires_at"],
        "user": user,
    }


@app.get("/api/auth/me")
def get_me(current_user: dict[str, object] = Depends(require_auth)) -> dict[str, object]:
    return current_user


@app.post("/api/auth/logout")
def logout(
    credentials=Depends(bearer_scheme),
    current_user: dict[str, object] = Depends(require_auth),
) -> dict[str, str]:
    delete_session(credentials.credentials)
    return {"status": "logged_out"}


@app.get("/api/overview")
def get_overview(current_user: dict[str, object] = Depends(require_auth)) -> dict[str, object]:
    return get_forecast_service().get_overview()


@app.get("/api/forecast/{department}")
def get_forecast(
    department: str,
    horizon_hours: int = Query(default=DEFAULT_FORECAST_HOURS, ge=6, le=168),
    current_user: dict[str, object] = Depends(require_auth),
) -> dict[str, object]:
    try:
        return get_forecast_service().get_forecast(department, horizon_hours)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@app.get("/api/alerts")
def get_alerts(
    horizon_hours: int = Query(default=DEFAULT_FORECAST_HOURS, ge=6, le=168),
    threshold: float | None = Query(default=None, ge=0.5, le=1.0),
    current_user: dict[str, object] = Depends(require_auth),
) -> list[dict[str, object]]:
    return get_forecast_service().get_alerts(horizon_hours=horizon_hours, threshold=threshold)


@app.get("/api/trends")
def get_trends(
    history_hours: int = Query(default=168, ge=24, le=336),
    current_user: dict[str, object] = Depends(require_auth),
) -> dict[str, object]:
    return get_forecast_service().get_trends(history_hours=history_hours)


@app.get("/api/dashboard")
def get_dashboard(
    horizon_hours: int = Query(default=DEFAULT_FORECAST_HOURS, ge=6, le=168),
    current_user: dict[str, object] = Depends(require_auth),
) -> dict[str, object]:
    return get_forecast_service().get_dashboard_payload(horizon_hours=horizon_hours)


@app.get("/api/admin/thresholds")
def admin_get_thresholds(current_user: dict[str, object] = Depends(require_admin)) -> dict[str, float]:
    return get_thresholds()


@app.put("/api/admin/thresholds")
def admin_update_thresholds(
    payload: ThresholdUpdateRequest,
    current_user: dict[str, object] = Depends(require_admin),
) -> dict[str, float]:
    for department, threshold in payload.thresholds.items():
        if department not in get_forecast_service().capacities:
            raise HTTPException(status_code=400, detail=f"Unknown department: {department}")
        if not 0.5 <= threshold <= 1.0:
            raise HTTPException(status_code=400, detail="Thresholds must be between 0.5 and 1.0.")
    return update_thresholds(payload.thresholds, str(current_user["username"]))


@app.get("/api/admin/alerts/history")
def admin_get_alert_history(
    limit: int = Query(default=50, ge=1, le=200),
    current_user: dict[str, object] = Depends(require_admin),
) -> list[dict[str, object]]:
    return get_alert_history(limit=limit)


@app.get("/api/admin/scenarios")
def admin_list_scenarios(current_user: dict[str, object] = Depends(require_admin)) -> list[dict[str, object]]:
    return list_scenarios()


@app.post("/api/admin/scenarios")
def admin_save_scenario(
    payload: ScenarioPayload,
    current_user: dict[str, object] = Depends(require_admin),
) -> dict[str, object]:
    try:
        return upsert_scenario(payload.model_dump(exclude_none=True), str(current_user["username"]))
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@app.delete("/api/admin/scenarios/{scenario_id}")
def admin_delete_scenario(
    scenario_id: int,
    current_user: dict[str, object] = Depends(require_admin),
) -> dict[str, str]:
    delete_scenario(scenario_id)
    return {"status": "deleted"}


@app.post("/api/admin/scenarios/{scenario_id}/simulate")
def admin_simulate_scenario(
    scenario_id: int,
    horizon_hours: int | None = Query(default=None, ge=6, le=168),
    current_user: dict[str, object] = Depends(require_admin),
) -> dict[str, object]:
    scenario = get_scenario(scenario_id)
    if scenario is None:
        raise HTTPException(status_code=404, detail="Scenario not found.")

    simulation = get_forecast_service().simulate_scenario(scenario, horizon_hours=horizon_hours)
    update_scenario_last_run(scenario_id, {"generated_at": simulation["generated_at"], "summary": simulation["summary"]})
    return simulation


@app.get("/api/admin/datasets/metadata")
def admin_get_dataset_metadata(current_user: dict[str, object] = Depends(require_admin)) -> dict[str, object]:
    return get_forecast_service().get_dataset_status()


@app.post("/api/admin/datasets/ingest")
def admin_ingest_dataset(
    payload: CsvIngestionRequest,
    current_user: dict[str, object] = Depends(require_admin),
) -> dict[str, object]:
    try:
        normalized_frame, metadata = normalize_his_dataset(payload.csv_text, payload.dataset_name)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    save_training_dataset(normalized_frame, metadata, raw_csv_text=payload.csv_text)
    save_dataset_metadata(metadata)
    service = reset_forecast_service()
    return {
        "status": "ingested",
        "dataset": service.get_dataset_status(),
    }


@app.post("/api/admin/models/retrain")
def admin_retrain_models(current_user: dict[str, object] = Depends(require_admin)) -> dict[str, object]:
    service = reset_forecast_service()
    return {"status": "retrained", "dataset": service.get_dataset_status()}
