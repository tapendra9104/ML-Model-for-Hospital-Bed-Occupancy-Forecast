# Machine Learning Based Hospital Bed Occupancy Forecasting System

Full-stack hospital operations dashboard with:

- FastAPI forecasting backend
- Real HIS CSV ingestion and retraining
- Persistent authentication, thresholds, scenarios, and alert history in SQLite
- React dashboard with lazy-loaded charts and split vendor bundles

## What Changed

- Real dataset support: event-level HIS exports (`admission_time`, `discharge_time`, `department`) and aggregated hourly occupancy CSVs can replace the synthetic seed data.
- Model retraining: uploaded HIS data is normalized into the hourly training frame and the forecasting models retrain against hospital-specific patterns.
- Authentication: all API routes except `/health` and `/api/auth/login` now require a bearer token.
- Persistence: SQLite stores users, sessions, alert thresholds, alert history, dataset metadata, and scenario definitions.
- Frontend bundle split: chart modules are lazy loaded and Vite outputs dedicated `vendor-react` and `vendor-charts` chunks without the prior size warning.

## Default Login

```text
username: admin
password: admin123
```

Override with environment variables before starting the backend:

```powershell
$env:HOSPITAL_ADMIN_USERNAME = "your-admin"
$env:HOSPITAL_ADMIN_PASSWORD = "strong-password"
```

## Architecture

```text
HIS / Admission-Discharge Export
              |
              v
CSV Ingestion + Normalization
              |
              v
Hourly Training Dataset
              |
              v
Feature Engineering + Forecast Models
              |
              v
FastAPI Auth + Prediction + Admin API
              |
              v
React Command Center Dashboard
```

## Repository Layout

```text
backend/
  app/
    auth.py
    config.py
    data_loader.py
    features.py
    forecasting.py
    main.py
    persistence.py
    schemas.py
    services.py
  tests/
frontend/
  src/
    components/
```

## Supported HIS CSV Formats

### 1. Event-level admission/discharge export

Required columns:

- `admission_time`
- `discharge_time` (optional but strongly recommended)
- `department`

Optional columns:

- `patient_id`
- `admission_type`

The backend converts these rows into hourly admissions, discharges, emergency inflow, and department occupancy counts.

### 2. Aggregated hourly occupancy dataset

Required columns:

- `timestamp`
- `admissions`
- `discharges`
- `icu_occupied`
- `ward_occupied`
- `emergency_occupied`
- `pediatric_occupied`

Optional columns:

- `emergency_cases`
- `outbreak_signal`

## Included Templates

- Event-level template: `backend/data/templates/his_event_template.csv`
- Aggregated hourly template: `backend/data/templates/his_aggregate_template.csv`

These are ready to upload through the admin UI or the `/api/admin/datasets/ingest` endpoint.

## Postman Collection

- Collection path: `postman/HospitalBedForecasting.postman_collection.json`

The collection includes:

- login and token capture
- dashboard and forecast requests
- threshold updates
- alert history
- dataset ingestion and retraining
- scenario creation and simulation

## Seed Script

Generate multiple hospital-profile HIS exports and normalized hourly datasets:

```powershell
python backend\scripts\seed_hospital_datasets.py
```

Output profiles are written under `backend/data/seeds/`:

- `metro_general`
- `community_care`
- `pediatric_specialty`

## API Endpoints

Public:

- `GET /health`
- `POST /api/auth/login`

Authenticated:

- `GET /api/auth/me`
- `POST /api/auth/logout`
- `GET /api/dashboard`
- `GET /api/overview`
- `GET /api/forecast/{department}`
- `GET /api/alerts`
- `GET /api/trends`

Admin:

- `GET /api/admin/thresholds`
- `PUT /api/admin/thresholds`
- `GET /api/admin/alerts/history`
- `GET /api/admin/scenarios`
- `POST /api/admin/scenarios`
- `DELETE /api/admin/scenarios/{id}`
- `POST /api/admin/scenarios/{id}/simulate`
- `GET /api/admin/datasets/metadata`
- `POST /api/admin/datasets/ingest`
- `POST /api/admin/models/retrain`

## Run Backend

```powershell
python -m pip install -r backend\requirements.txt
uvicorn backend.app.main:app --reload
```

Optional environment variables:

```powershell
$env:HOSPITAL_APP_DB_PATH = "C:\path\to\hospital_app.sqlite3"
$env:HOSPITAL_ACTIVITY_DATA_PATH = "C:\path\to\hospital_activity.csv"
$env:HOSPITAL_HIS_RAW_DATA_PATH = "C:\path\to\his_source.csv"
```

## Run Frontend

```powershell
cd frontend
npm install
npm run dev
```

Open `http://127.0.0.1:5173` and sign in.

## Verification

```powershell
python -m pytest -q backend\tests
cd frontend
npm run build
```

## Notes

- The project still seeds synthetic data automatically when no HIS dataset is present.
- Uploaded real HIS data replaces the training dataset and becomes the active forecasting source.
- Scenario simulations are intentionally non-destructive: they do not write hypothetical alerts into persisted alert history.
