from __future__ import annotations

import io
import re
from pathlib import Path

import numpy as np
import pandas as pd

from .config import DATA_PATH, DEFAULT_CAPACITIES, DEPARTMENTS, MIN_TRAINING_ROWS, RAW_HIS_DATA_PATH, occupancy_column, round_capacity

AGGREGATE_ALIASES = {
    "timestamp": ["timestamp", "datetime", "date_time", "recorded_at", "date", "hour"],
    "admissions": ["admissions", "admission_count", "admit_count", "admitted"],
    "discharges": ["discharges", "discharge_count", "released_count", "released"],
    "emergency_cases": ["emergency_cases", "emergency_admissions", "er_cases", "ed_cases"],
    "outbreak_signal": ["outbreak_signal", "outbreak_index", "surge_signal"],
    "icu_occupied": ["icu_occupied", "icu_beds_occupied", "icu_occupancy"],
    "ward_occupied": ["ward_occupied", "ward_beds_occupied", "general_ward_occupancy"],
    "emergency_occupied": ["emergency_occupied", "emergency_beds_occupied", "emergency_occupancy"],
    "pediatric_occupied": ["pediatric_occupied", "pediatric_beds_occupied", "pediatric_occupancy"],
}

EVENT_ALIASES = {
    "patient_id": ["patient_id", "encounter_id", "visit_id"],
    "admission_time": ["admission_time", "admit_time", "admitted_at", "admission_datetime"],
    "discharge_time": ["discharge_time", "discharged_at", "departure_time", "discharge_datetime"],
    "department": ["department", "unit", "ward", "bed_type", "care_unit"],
    "admission_type": ["admission_type", "visit_type", "source", "encounter_type"],
}

OCCUPANCY_COLUMNS = [occupancy_column(department) for department in DEPARTMENTS]


def _clean_column_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.strip().lower()).strip("_")


def _rename_known_columns(frame: pd.DataFrame, alias_map: dict[str, list[str]]) -> pd.DataFrame:
    normalized_lookup = {_clean_column_name(column): column for column in frame.columns}
    rename_map: dict[str, str] = {}
    for canonical, aliases in alias_map.items():
        for alias in aliases:
            if alias in normalized_lookup:
                rename_map[normalized_lookup[alias]] = canonical
                break
    return frame.rename(columns=rename_map)


def _derive_outbreak_signal(frame: pd.DataFrame) -> pd.Series:
    baseline = frame["admissions"].rolling(24 * 7, min_periods=24).mean()
    baseline = baseline.fillna(frame["admissions"].expanding().mean())
    volatility = frame["admissions"].rolling(24 * 7, min_periods=24).std().replace(0, np.nan)
    volatility = volatility.fillna(frame["admissions"].std() or 1.0)

    emergency_baseline = frame["emergency_cases"].rolling(24 * 7, min_periods=24).mean()
    emergency_baseline = emergency_baseline.fillna(frame["emergency_cases"].expanding().mean())
    emergency_volatility = frame["emergency_cases"].rolling(24 * 7, min_periods=24).std().replace(0, np.nan)
    emergency_volatility = emergency_volatility.fillna(frame["emergency_cases"].std() or 1.0)

    admissions_anomaly = ((frame["admissions"] - baseline) / volatility).clip(lower=0)
    emergency_anomaly = ((frame["emergency_cases"] - emergency_baseline) / emergency_volatility).clip(lower=0)
    combined = (0.7 * admissions_anomaly) + (0.3 * emergency_anomaly)
    scale = max(float(combined.max()), 1.0)
    return (combined / scale).fillna(0).clip(0, 1)


def validate_training_frame(frame: pd.DataFrame) -> None:
    if len(frame) < MIN_TRAINING_ROWS:
        raise ValueError(
            f"Dataset must contain at least {MIN_TRAINING_ROWS} hourly rows after preprocessing."
        )


def infer_capacities(frame: pd.DataFrame) -> dict[str, int]:
    capacities: dict[str, int] = {}
    for department, default_capacity in DEFAULT_CAPACITIES.items():
        observed_peak = float(frame[occupancy_column(department)].max()) if occupancy_column(department) in frame else 0.0
        buffered_capacity = max(default_capacity, observed_peak * 1.12)
        capacities[department] = round_capacity(buffered_capacity)
    return capacities


def build_dataset_metadata(frame: pd.DataFrame, source_name: str, source_type: str) -> dict[str, object]:
    return {
        "source_name": source_name,
        "source_type": source_type,
        "rows": int(len(frame)),
        "coverage_start": pd.Timestamp(frame["timestamp"].min()).isoformat(),
        "coverage_end": pd.Timestamp(frame["timestamp"].max()).isoformat(),
        "capacities": infer_capacities(frame),
    }


def generate_synthetic_dataset(output_path: Path, periods: int = 24 * 180) -> pd.DataFrame:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    rng = np.random.default_rng(42)
    timeline = pd.date_range(end=pd.Timestamp.now().floor("h"), periods=periods, freq="h")
    occupancy = {"icu": 32.0, "ward": 178.0, "emergency": 24.0, "pediatric": 16.0}
    outbreak_pressure = 0.0
    rows: list[dict[str, float | int | str]] = []

    for timestamp in timeline:
        hour = timestamp.hour
        day_of_week = timestamp.dayofweek
        day_of_year = timestamp.dayofyear
        month = timestamp.month
        is_weekend = int(day_of_week >= 5)

        circadian = 0.18 * np.sin((2 * np.pi * hour) / 24)
        weekly = 0.12 * np.cos((2 * np.pi * day_of_week) / 7)
        yearly = 0.22 * np.sin((2 * np.pi * day_of_year) / 365)
        winter_pressure = 0.20 if month in {12, 1, 2} else 0.0
        monsoon_pressure = 0.10 if month in {7, 8, 9} else 0.0

        if rng.random() < 0.01:
            outbreak_pressure += rng.uniform(0.25, 0.6)
        outbreak_pressure *= 0.92
        outbreak_pressure = float(np.clip(outbreak_pressure, 0.0, 1.0))

        admissions_signal = 88 + (18 * circadian) + (8 * weekly) + (14 * yearly)
        admissions_signal += 16 * winter_pressure + 8 * monsoon_pressure + 34 * outbreak_pressure
        admissions_signal += -10 if is_weekend else 6
        admissions = max(26, int(round(admissions_signal + rng.normal(0, 7))))

        emergency_signal = 22 + (10 * max(circadian, 0)) + (6 * yearly)
        emergency_signal += 7 * monsoon_pressure + 12 * outbreak_pressure
        emergency_cases = max(4, int(round(emergency_signal + rng.normal(0, 3))))

        discharge_signal = 74 + (8 * np.cos((2 * np.pi * hour) / 24)) - (5 * yearly)
        discharge_signal += -9 if is_weekend else 5
        discharge_signal += 0.18 * occupancy["ward"] + 0.12 * occupancy["icu"]
        discharges = max(18, int(round(discharge_signal + rng.normal(0, 6))))

        icu_target = 29 + (0.14 * admissions) + (0.42 * emergency_cases) + (18 * outbreak_pressure)
        icu_target += 4 * winter_pressure - (0.18 * discharges)
        ward_target = 150 + (0.82 * admissions) - (0.55 * discharges) + (18 * yearly)
        ward_target += 22 * outbreak_pressure + 10 * winter_pressure
        emergency_target = 18 + (0.95 * emergency_cases) + (0.12 * admissions)
        emergency_target += 10 * outbreak_pressure - (0.06 * discharges)
        pediatric_target = 12 + (0.16 * admissions) + (0.15 * emergency_cases)
        pediatric_target += 14 * winter_pressure + 4 * outbreak_pressure - (0.10 * discharges)

        occupancy["icu"] = float(np.clip((0.80 * occupancy["icu"]) + (0.20 * icu_target) + rng.normal(0, 1.2), 8, DEFAULT_CAPACITIES["icu"]))
        occupancy["ward"] = float(np.clip((0.86 * occupancy["ward"]) + (0.14 * ward_target) + rng.normal(0, 3.4), 55, DEFAULT_CAPACITIES["ward"]))
        occupancy["emergency"] = float(np.clip((0.74 * occupancy["emergency"]) + (0.26 * emergency_target) + rng.normal(0, 1.8), 6, DEFAULT_CAPACITIES["emergency"]))
        occupancy["pediatric"] = float(np.clip((0.78 * occupancy["pediatric"]) + (0.22 * pediatric_target) + rng.normal(0, 1.0), 3, DEFAULT_CAPACITIES["pediatric"]))

        rows.append(
            {
                "timestamp": timestamp.isoformat(),
                "admissions": admissions,
                "discharges": discharges,
                "emergency_cases": emergency_cases,
                "outbreak_signal": round(outbreak_pressure, 3),
                "icu_occupied": round(occupancy["icu"], 2),
                "ward_occupied": round(occupancy["ward"], 2),
                "emergency_occupied": round(occupancy["emergency"], 2),
                "pediatric_occupied": round(occupancy["pediatric"], 2),
            }
        )

    frame = pd.DataFrame(rows)
    frame["total_occupied"] = frame[OCCUPANCY_COLUMNS].sum(axis=1)
    frame.to_csv(output_path, index=False)
    return frame


def load_dataset(data_path: Path) -> pd.DataFrame:
    if not data_path.exists():
        return generate_synthetic_dataset(data_path)

    frame = pd.read_csv(data_path, parse_dates=["timestamp"])
    if frame.empty:
        return generate_synthetic_dataset(data_path)

    frame = frame.sort_values("timestamp").reset_index(drop=True)
    if "outbreak_signal" not in frame:
        frame["outbreak_signal"] = _derive_outbreak_signal(frame)
    frame["total_occupied"] = frame[OCCUPANCY_COLUMNS].sum(axis=1)
    return frame


def save_training_dataset(frame: pd.DataFrame, metadata: dict[str, object], raw_csv_text: str | None = None) -> None:
    DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(DATA_PATH, index=False)
    if raw_csv_text:
        RAW_HIS_DATA_PATH.write_text(raw_csv_text, encoding="utf-8")


def _department_from_text(department_text: str, admission_type: str) -> str:
    combined = f"{department_text} {admission_type}".strip().lower()
    normalized = re.sub(r"[^a-z]+", " ", combined)
    if any(keyword in normalized for keyword in ["pediatric", "paediatric", "child", "nicu", "picu"]):
        return "pediatric"
    if any(keyword in normalized for keyword in ["emergency", "trauma", "casualty"]):
        return "emergency"
    if re.search(r"\ber\b|\bed\b", normalized):
        return "emergency"
    if any(keyword in normalized for keyword in ["icu", "intensive", "critical"]):
        return "icu"
    return "ward"


def _normalize_aggregate_frame(frame: pd.DataFrame, dataset_name: str) -> tuple[pd.DataFrame, dict[str, object]]:
    renamed = _rename_known_columns(frame, AGGREGATE_ALIASES)
    required = {"timestamp", "admissions", "discharges", *OCCUPANCY_COLUMNS}
    missing = [column for column in required if column not in renamed.columns]
    if missing:
        raise ValueError(
            "Aggregate dataset is missing required columns: " + ", ".join(sorted(missing))
        )

    working = renamed.copy()
    working["timestamp"] = pd.to_datetime(working["timestamp"], errors="coerce")
    working = working.dropna(subset=["timestamp"]).copy()
    for column in ["admissions", "discharges", "emergency_cases", "outbreak_signal", *OCCUPANCY_COLUMNS]:
        if column not in working:
            working[column] = 0
        working[column] = pd.to_numeric(working[column], errors="coerce").fillna(0)

    working = (
        working.groupby(pd.Grouper(key="timestamp", freq="h"))
        .agg(
            {
                "admissions": "sum",
                "discharges": "sum",
                "emergency_cases": "sum",
                "outbreak_signal": "mean",
                "icu_occupied": "mean",
                "ward_occupied": "mean",
                "emergency_occupied": "mean",
                "pediatric_occupied": "mean",
            }
        )
        .reset_index()
    )
    working["outbreak_signal"] = working["outbreak_signal"].fillna(_derive_outbreak_signal(working))
    working["total_occupied"] = working[OCCUPANCY_COLUMNS].sum(axis=1)
    validate_training_frame(working)
    metadata = build_dataset_metadata(working, dataset_name, "aggregate_his")
    return working, metadata


def _normalize_event_frame(frame: pd.DataFrame, dataset_name: str) -> tuple[pd.DataFrame, dict[str, object]]:
    renamed = _rename_known_columns(frame, EVENT_ALIASES)
    if "admission_time" not in renamed.columns:
        raise ValueError("Event-level HIS dataset requires an admission_time column.")

    working = renamed.copy()
    if "department" not in working.columns:
        working["department"] = "general ward"
    if "admission_type" not in working.columns:
        working["admission_type"] = ""
    if "discharge_time" not in working.columns:
        working["discharge_time"] = pd.NaT

    working["admission_time"] = pd.to_datetime(working["admission_time"], errors="coerce")
    working["discharge_time"] = pd.to_datetime(working["discharge_time"], errors="coerce")
    working = working.dropna(subset=["admission_time"]).copy()
    working["department"] = working["department"].fillna("general ward")
    working["admission_type"] = working["admission_type"].fillna("")
    working["mapped_department"] = working.apply(
        lambda row: _department_from_text(str(row["department"]), str(row["admission_type"])),
        axis=1,
    )

    observed_lengths = (
        working["discharge_time"] - working["admission_time"]
    ).dt.total_seconds().div(3600)
    default_length = max(12.0, float(observed_lengths.dropna().median() if observed_lengths.dropna().any() else 36.0))
    default_stay = pd.Timedelta(hours=default_length)
    working["discharge_time"] = working["discharge_time"].fillna(working["admission_time"] + default_stay)
    invalid_discharge = working["discharge_time"] <= working["admission_time"]
    working.loc[invalid_discharge, "discharge_time"] = working.loc[invalid_discharge, "admission_time"] + default_stay

    working["admission_bucket"] = working["admission_time"].dt.floor("h")
    working["discharge_bucket"] = working["discharge_time"].dt.ceil("h")
    same_bucket = working["discharge_bucket"] <= working["admission_bucket"]
    working.loc[same_bucket, "discharge_bucket"] = working.loc[same_bucket, "admission_bucket"] + pd.Timedelta(hours=1)

    timeline = pd.date_range(
        start=working["admission_bucket"].min(),
        end=working["discharge_bucket"].max(),
        freq="h",
    )

    normalized = pd.DataFrame({"timestamp": timeline})
    normalized["admissions"] = working.groupby("admission_bucket").size().reindex(timeline, fill_value=0).astype(int).values
    normalized["discharges"] = working.groupby("discharge_bucket").size().reindex(timeline, fill_value=0).astype(int).values

    emergency_mask = (
        working["mapped_department"].eq("emergency")
        | working["admission_type"].astype(str).str.contains("emerg|urgent|trauma|er|ed", case=False, regex=True)
    )
    normalized["emergency_cases"] = (
        working.loc[emergency_mask]
        .groupby("admission_bucket")
        .size()
        .reindex(timeline, fill_value=0)
        .astype(int)
        .values
    )

    for department in DEPARTMENTS:
        subset = working.loc[working["mapped_department"] == department]
        starts = subset.groupby("admission_bucket").size().reindex(timeline, fill_value=0)
        ends = subset.groupby("discharge_bucket").size().reindex(timeline, fill_value=0)
        occupancy = starts.sub(ends, fill_value=0).cumsum().clip(lower=0)
        normalized[occupancy_column(department)] = occupancy.astype(float).values

    normalized["outbreak_signal"] = _derive_outbreak_signal(normalized)
    normalized["total_occupied"] = normalized[OCCUPANCY_COLUMNS].sum(axis=1)
    validate_training_frame(normalized)
    metadata = build_dataset_metadata(normalized, dataset_name, "event_level_his")
    return normalized, metadata


def normalize_his_dataset(csv_text: str, dataset_name: str) -> tuple[pd.DataFrame, dict[str, object]]:
    try:
        frame = pd.read_csv(io.StringIO(csv_text))
    except Exception as error:
        raise ValueError(f"Unable to parse CSV data: {error}") from error

    normalized_columns = {_clean_column_name(column) for column in frame.columns}
    event_aliases = {alias for aliases in EVENT_ALIASES.values() for alias in aliases}
    if any(alias in normalized_columns for alias in event_aliases if alias.startswith("admission")):
        return _normalize_event_frame(frame, dataset_name)
    return _normalize_aggregate_frame(frame, dataset_name)
