from __future__ import annotations

from functools import lru_cache

import pandas as pd

from .config import DEFAULT_ALERT_THRESHOLD, DEFAULT_CAPACITIES, DATA_PATH, DEFAULT_FORECAST_HOURS, DEPARTMENT_LABELS, DEPARTMENTS, FORECAST_LIMIT_HOURS, occupancy_column
from .data_loader import build_dataset_metadata, infer_capacities, load_dataset, validate_training_frame
from .features import build_future_feature_row, build_training_frame
from .forecasting import DepartmentForecastModel, train_department_model
from .persistence import get_dataset_metadata, get_thresholds, record_alerts, save_dataset_metadata, utcnow_iso


class HospitalForecastService:
    def __init__(self) -> None:
        self.frame = load_dataset(DATA_PATH)
        self.frame["timestamp"] = pd.to_datetime(self.frame["timestamp"])
        self.frame = self.frame.sort_values("timestamp").reset_index(drop=True)
        validate_training_frame(self.frame)

        self.capacities = infer_capacities(self.frame)
        self.trained_at = utcnow_iso()
        self.dataset_metadata = get_dataset_metadata() or build_dataset_metadata(
            self.frame,
            source_name="synthetic_seed",
            source_type="synthetic",
        )
        self.dataset_metadata["capacities"] = self.capacities
        self.dataset_metadata["trained_at"] = self.trained_at
        save_dataset_metadata(self.dataset_metadata)

        self.exogenous_profile = self._build_exogenous_profile()
        self.department_models = self._train_models()

    def _build_exogenous_profile(self) -> dict[tuple[int, int], dict[str, float]]:
        grouped = (
            self.frame.assign(
                hour=self.frame["timestamp"].dt.hour,
                day_of_week=self.frame["timestamp"].dt.dayofweek,
            )
            .groupby(["day_of_week", "hour"])[["admissions", "discharges", "emergency_cases", "outbreak_signal"]]
            .mean()
        )
        return {
            (int(day), int(hour)): {column: float(value) for column, value in row.items()}
            for (day, hour), row in grouped.iterrows()
        }

    def _train_models(self) -> dict[str, DepartmentForecastModel]:
        models: dict[str, DepartmentForecastModel] = {}
        for department in DEPARTMENTS:
            target_column = occupancy_column(department)
            training_frame, feature_columns = build_training_frame(self.frame, target_column)
            if training_frame.empty:
                raise ValueError(f"Insufficient training rows for {department} forecast model.")
            models[department] = train_department_model(training_frame, target_column, feature_columns)
        return models

    def _project_exogenous(self, timestamp: pd.Timestamp) -> dict[str, float]:
        key = (timestamp.dayofweek, timestamp.hour)
        return self.exogenous_profile[key]

    def _scenario_adjusted_exogenous(
        self,
        exogenous_values: dict[str, float],
        scenario: dict[str, object] | None,
        step: int,
    ) -> dict[str, float]:
        if not scenario or step > int(scenario.get("duration_hours", DEFAULT_FORECAST_HOURS)):
            return dict(exogenous_values)

        adjusted = dict(exogenous_values)
        adjusted["admissions"] = float(adjusted["admissions"] * float(scenario.get("admissions_multiplier", 1.0)))
        adjusted["discharges"] = float(adjusted["discharges"] * float(scenario.get("discharges_multiplier", 1.0)))
        adjusted["emergency_cases"] = float(adjusted["emergency_cases"] * float(scenario.get("emergency_multiplier", 1.0)))
        adjusted["outbreak_signal"] = max(
            0.0,
            min(1.0, float(adjusted["outbreak_signal"]) + float(scenario.get("outbreak_delta", 0.0))),
        )
        return adjusted

    def _resolve_thresholds(self, override: float | None = None) -> dict[str, float]:
        if override is not None:
            return {department: float(override) for department in DEPARTMENTS}

        stored_thresholds = get_thresholds()
        return {
            department: float(stored_thresholds.get(department, DEFAULT_ALERT_THRESHOLD))
            for department in DEPARTMENTS
        }

    def get_dataset_status(self) -> dict[str, object]:
        return {
            **self.dataset_metadata,
            "trained_at": self.trained_at,
            "model_metrics": {
                department: {
                    "rmse": round(model.rmse, 2),
                    "capacity": self.capacities[department],
                }
                for department, model in self.department_models.items()
            },
        }

    def get_overview(self) -> dict[str, object]:
        latest = self.frame.iloc[-1]
        comparison = self.frame.iloc[-25] if len(self.frame) > 25 else self.frame.iloc[0]

        departments: list[dict[str, object]] = []
        total_capacity = sum(self.capacities.values())
        total_occupied = 0.0

        for department in DEPARTMENTS:
            target_column = occupancy_column(department)
            occupied = float(latest[target_column])
            previous = float(comparison[target_column])
            capacity = self.capacities[department]
            available = capacity - occupied
            utilization = occupied / capacity if capacity else 0.0
            total_occupied += occupied

            departments.append(
                {
                    "id": department,
                    "label": DEPARTMENT_LABELS[department],
                    "capacity": capacity,
                    "occupied": round(occupied, 1),
                    "available": round(available, 1),
                    "utilization": round(utilization, 3),
                    "delta_24h": round(occupied - previous, 1),
                }
            )

        peak_hour = (
            self.frame.assign(hour=self.frame["timestamp"].dt.hour)
            .groupby("hour")["admissions"]
            .mean()
            .idxmax()
        )
        busiest_day = (
            self.frame.assign(day=self.frame["timestamp"].dt.day_name())
            .groupby("day")["admissions"]
            .mean()
            .sort_values(ascending=False)
            .index[0]
        )
        average_stay_hours = max(
            8.0,
            round((self.frame["ward_occupied"].mean() / max(self.frame["discharges"].mean(), 1)) * 24, 1),
        )

        return {
            "generated_at": utcnow_iso(),
            "hospital": {
                "total_capacity": total_capacity,
                "occupied": round(total_occupied, 1),
                "available": round(total_capacity - total_occupied, 1),
                "utilization": round(total_occupied / total_capacity, 3) if total_capacity else 0.0,
            },
            "departments": departments,
            "analytics": {
                "peak_admission_hour": f"{int(peak_hour):02d}:00",
                "busiest_day": busiest_day,
                "average_length_of_stay_hours": average_stay_hours,
                "outbreak_pressure_index": round(float(latest["outbreak_signal"]), 3),
            },
            "dataset": {
                "source_name": self.dataset_metadata.get("source_name", "synthetic_seed"),
                "source_type": self.dataset_metadata.get("source_type", "synthetic"),
                "trained_at": self.trained_at,
            },
        }

    def get_forecast(
        self,
        department: str,
        horizon_hours: int = DEFAULT_FORECAST_HOURS,
        scenario: dict[str, object] | None = None,
    ) -> dict[str, object]:
        if department not in DEPARTMENTS:
            raise ValueError(f"Unknown department: {department}")

        horizon_hours = max(6, min(int(horizon_hours), FORECAST_LIMIT_HOURS))
        department_model = self.department_models[department]
        target_column = department_model.target_column
        department_history = self.frame[["timestamp", "admissions", "discharges", "emergency_cases", "outbreak_signal", target_column]].copy()
        current_timestamp = pd.Timestamp(department_history["timestamp"].iloc[-1])
        capacity = self.capacities[department]
        occupancy_delta = float(scenario.get("occupancy_delta", 0.0)) if scenario else 0.0

        points: list[dict[str, object]] = []
        for step in range(1, horizon_hours + 1):
            future_timestamp = current_timestamp + pd.Timedelta(hours=step)
            exogenous_values = self._project_exogenous(future_timestamp)
            adjusted_exogenous = self._scenario_adjusted_exogenous(exogenous_values, scenario, step)
            feature_row = build_future_feature_row(
                history=department_history,
                target_column=target_column,
                future_timestamp=future_timestamp,
                exogenous_values=adjusted_exogenous,
            )
            predicted_value = department_model.predict(feature_row)
            if scenario and step <= int(scenario.get("duration_hours", horizon_hours)):
                predicted_value += occupancy_delta
            predicted_value = max(0.0, min(float(capacity), predicted_value))

            lower = max(0.0, predicted_value - (1.96 * department_model.rmse))
            upper = min(float(capacity), predicted_value + (1.96 * department_model.rmse))

            points.append(
                {
                    "timestamp": future_timestamp.isoformat(),
                    "occupied": round(predicted_value, 1),
                    "lower": round(lower, 1),
                    "upper": round(upper, 1),
                    "utilization": round(predicted_value / capacity, 3) if capacity else 0.0,
                }
            )

            next_row = {
                "timestamp": future_timestamp,
                target_column: predicted_value,
                **adjusted_exogenous,
            }
            department_history.loc[len(department_history)] = next_row

        peak_point = max(points, key=lambda point: point["occupied"])
        return {
            "department": department,
            "label": DEPARTMENT_LABELS[department],
            "capacity": capacity,
            "generated_at": utcnow_iso(),
            "horizon_hours": horizon_hours,
            "summary": {
                "peak_occupancy": peak_point["occupied"],
                "peak_timestamp": peak_point["timestamp"],
                "threshold_crossing": peak_point if peak_point["utilization"] >= DEFAULT_ALERT_THRESHOLD else None,
            },
            "scenario": {"name": scenario.get("name")} if scenario else None,
            "points": points,
        }

    def _alerts_from_forecasts(
        self,
        forecasts: list[dict[str, object]],
        thresholds: dict[str, float],
        persist: bool = True,
    ) -> list[dict[str, object]]:
        alerts: list[dict[str, object]] = []
        for forecast in forecasts:
            threshold = float(thresholds.get(forecast["department"], DEFAULT_ALERT_THRESHOLD))
            for point in forecast["points"]:
                if float(point["utilization"]) < threshold:
                    continue

                severity = "critical" if float(point["utilization"]) >= min(1.0, threshold + 0.07) else "warning"
                alerts.append(
                    {
                        "department": forecast["department"],
                        "label": forecast["label"],
                        "timestamp": point["timestamp"],
                        "utilization": point["utilization"],
                        "threshold": round(threshold, 3),
                        "severity": severity,
                        "message": (
                            f"{forecast['label']} occupancy is forecast to reach "
                            f"{round(float(point['utilization']) * 100)}% against a "
                            f"{round(threshold * 100)}% threshold."
                        ),
                    }
                )
                break

        ordered_alerts = sorted(alerts, key=lambda alert: alert["utilization"], reverse=True)
        if persist:
            record_alerts(ordered_alerts)
        return ordered_alerts

    def get_alerts(
        self,
        horizon_hours: int = DEFAULT_FORECAST_HOURS,
        threshold: float | None = None,
    ) -> list[dict[str, object]]:
        forecasts = [self.get_forecast(department, horizon_hours) for department in DEPARTMENTS]
        return self._alerts_from_forecasts(forecasts, self._resolve_thresholds(threshold))

    def get_trends(self, history_hours: int = 24 * 7) -> dict[str, object]:
        history_hours = max(24, min(history_hours, FORECAST_LIMIT_HOURS * 2))
        recent = self.frame.tail(history_hours).copy()
        occupancy_history = []

        for _, row in recent.iterrows():
            occupancy_history.append(
                {
                    "timestamp": pd.Timestamp(row["timestamp"]).isoformat(),
                    "icu": round(float(row["icu_occupied"]), 1),
                    "ward": round(float(row["ward_occupied"]), 1),
                    "emergency": round(float(row["emergency_occupied"]), 1),
                    "pediatric": round(float(row["pediatric_occupied"]), 1),
                }
            )

        daily_flow = (
            self.frame.assign(day=self.frame["timestamp"].dt.strftime("%Y-%m-%d"))
            .groupby("day")[["admissions", "discharges", "emergency_cases"]]
            .sum()
            .tail(21)
            .reset_index()
        )
        flow_points = [
            {
                "date": row["day"],
                "admissions": int(row["admissions"]),
                "discharges": int(row["discharges"]),
                "emergency_cases": int(row["emergency_cases"]),
            }
            for _, row in daily_flow.iterrows()
        ]

        return {
            "generated_at": utcnow_iso(),
            "occupancy_history": occupancy_history,
            "daily_flow": flow_points,
        }

    def simulate_scenario(
        self,
        scenario: dict[str, object],
        horizon_hours: int | None = None,
    ) -> dict[str, object]:
        effective_horizon = horizon_hours or int(scenario.get("duration_hours", DEFAULT_FORECAST_HOURS))
        forecasts = [
            self.get_forecast(department, effective_horizon, scenario=scenario)
            for department in DEPARTMENTS
        ]
        thresholds = self._resolve_thresholds()
        alerts = self._alerts_from_forecasts(forecasts, thresholds, persist=False)
        summary = [
            {
                "department": forecast["department"],
                "label": forecast["label"],
                "peak_occupancy": forecast["summary"]["peak_occupancy"],
                "peak_timestamp": forecast["summary"]["peak_timestamp"],
                "capacity": forecast["capacity"],
            }
            for forecast in forecasts
        ]
        return {
            "scenario": scenario,
            "generated_at": utcnow_iso(),
            "forecasts": forecasts,
            "alerts": alerts,
            "summary": summary,
        }

    def get_dashboard_payload(self, horizon_hours: int = DEFAULT_FORECAST_HOURS) -> dict[str, object]:
        forecasts = [self.get_forecast(department, horizon_hours) for department in DEPARTMENTS]
        thresholds = self._resolve_thresholds()
        return {
            "overview": self.get_overview(),
            "forecasts": forecasts,
            "alerts": self._alerts_from_forecasts(forecasts, thresholds),
            "trends": self.get_trends(),
            "thresholds": thresholds,
            "dataset": self.get_dataset_status(),
        }


@lru_cache
def get_forecast_service() -> HospitalForecastService:
    return HospitalForecastService()


def reset_forecast_service() -> HospitalForecastService:
    get_forecast_service.cache_clear()
    return get_forecast_service()
