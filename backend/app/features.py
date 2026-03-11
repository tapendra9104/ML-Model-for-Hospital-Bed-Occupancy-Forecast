from __future__ import annotations

import math

import pandas as pd

CALENDAR_FEATURES = [
    "hour",
    "day_of_week",
    "month",
    "is_weekend",
    "hour_sin",
    "hour_cos",
    "dow_sin",
    "dow_cos",
]

EXOGENOUS_FEATURES = [
    "admissions",
    "discharges",
    "emergency_cases",
    "outbreak_signal",
]

LAG_OFFSETS = (1, 2, 6, 24, 48, 72)
ROLLING_WINDOWS = (6, 24, 72)


def add_calendar_features(frame: pd.DataFrame) -> pd.DataFrame:
    enriched = frame.copy()
    enriched["hour"] = enriched["timestamp"].dt.hour
    enriched["day_of_week"] = enriched["timestamp"].dt.dayofweek
    enriched["month"] = enriched["timestamp"].dt.month
    enriched["is_weekend"] = (enriched["day_of_week"] >= 5).astype(int)
    enriched["hour_sin"] = enriched["hour"].apply(lambda hour: math.sin((2 * math.pi * hour) / 24))
    enriched["hour_cos"] = enriched["hour"].apply(lambda hour: math.cos((2 * math.pi * hour) / 24))
    enriched["dow_sin"] = enriched["day_of_week"].apply(lambda day: math.sin((2 * math.pi * day) / 7))
    enriched["dow_cos"] = enriched["day_of_week"].apply(lambda day: math.cos((2 * math.pi * day) / 7))
    return enriched


def build_training_frame(frame: pd.DataFrame, target_column: str) -> tuple[pd.DataFrame, list[str]]:
    training = add_calendar_features(frame)

    for lag in LAG_OFFSETS:
        training[f"{target_column}_lag_{lag}"] = training[target_column].shift(lag)

    for window in ROLLING_WINDOWS:
        training[f"{target_column}_rolling_mean_{window}"] = training[target_column].shift(1).rolling(window).mean()

    training["admissions_rolling_24"] = training["admissions"].shift(1).rolling(24).mean()
    training["discharges_rolling_24"] = training["discharges"].shift(1).rolling(24).mean()
    training["emergency_rolling_24"] = training["emergency_cases"].shift(1).rolling(24).mean()

    feature_columns = (
        CALENDAR_FEATURES
        + EXOGENOUS_FEATURES
        + [f"{target_column}_lag_{lag}" for lag in LAG_OFFSETS]
        + [f"{target_column}_rolling_mean_{window}" for window in ROLLING_WINDOWS]
        + ["admissions_rolling_24", "discharges_rolling_24", "emergency_rolling_24"]
    )

    training = training.dropna().reset_index(drop=True)
    return training, feature_columns


def build_future_feature_row(
    history: pd.DataFrame,
    target_column: str,
    future_timestamp: pd.Timestamp,
    exogenous_values: dict[str, float],
) -> dict[str, float]:
    row: dict[str, float] = {
        "hour": float(future_timestamp.hour),
        "day_of_week": float(future_timestamp.dayofweek),
        "month": float(future_timestamp.month),
        "is_weekend": float(int(future_timestamp.dayofweek >= 5)),
        "hour_sin": math.sin((2 * math.pi * future_timestamp.hour) / 24),
        "hour_cos": math.cos((2 * math.pi * future_timestamp.hour) / 24),
        "dow_sin": math.sin((2 * math.pi * future_timestamp.dayofweek) / 7),
        "dow_cos": math.cos((2 * math.pi * future_timestamp.dayofweek) / 7),
    }

    for feature_name in EXOGENOUS_FEATURES:
        row[feature_name] = float(exogenous_values[feature_name])

    target_history = history[target_column]

    for lag in LAG_OFFSETS:
        row[f"{target_column}_lag_{lag}"] = float(target_history.iloc[-lag])

    for window in ROLLING_WINDOWS:
        row[f"{target_column}_rolling_mean_{window}"] = float(target_history.iloc[-window:].mean())

    row["admissions_rolling_24"] = float(history["admissions"].iloc[-24:].mean())
    row["discharges_rolling_24"] = float(history["discharges"].iloc[-24:].mean())
    row["emergency_rolling_24"] = float(history["emergency_cases"].iloc[-24:].mean())
    return row
