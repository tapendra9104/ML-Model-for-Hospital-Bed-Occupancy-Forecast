from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from .config import DEFAULT_FORECAST_HOURS


class LoginRequest(BaseModel):
    username: str
    password: str


class ThresholdUpdateRequest(BaseModel):
    thresholds: dict[str, float]


class CsvIngestionRequest(BaseModel):
    dataset_name: str = Field(min_length=3, max_length=120)
    csv_text: str = Field(min_length=20)


class ScenarioPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: int | None = None
    name: str = Field(min_length=3, max_length=80)
    description: str = Field(default="", max_length=240)
    admissions_multiplier: float = Field(default=1.0, ge=0.2, le=5.0)
    discharges_multiplier: float = Field(default=1.0, ge=0.2, le=5.0)
    emergency_multiplier: float = Field(default=1.0, ge=0.2, le=5.0)
    outbreak_delta: float = Field(default=0.0, ge=-1.0, le=1.0)
    occupancy_delta: float = Field(default=0.0, ge=-100.0, le=100.0)
    duration_hours: int = Field(default=DEFAULT_FORECAST_HOURS, ge=6, le=168)
