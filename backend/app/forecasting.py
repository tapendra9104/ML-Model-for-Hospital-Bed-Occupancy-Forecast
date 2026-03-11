from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.metrics import mean_squared_error


@dataclass(slots=True)
class DepartmentForecastModel:
    target_column: str
    feature_columns: list[str]
    model: HistGradientBoostingRegressor
    rmse: float
    min_observed: float
    max_observed: float

    def predict(self, feature_row: dict[str, float]) -> float:
        frame = pd.DataFrame([feature_row], columns=self.feature_columns)
        return float(self.model.predict(frame)[0])


def train_department_model(
    training_frame: pd.DataFrame,
    target_column: str,
    feature_columns: list[str],
) -> DepartmentForecastModel:
    split_index = max(1, int(len(training_frame) * 0.85))
    train_frame = training_frame.iloc[:split_index]
    validation_frame = training_frame.iloc[split_index:]

    model = HistGradientBoostingRegressor(random_state=42, max_depth=6, max_iter=150, learning_rate=0.08)
    model.fit(train_frame[feature_columns], train_frame[target_column])

    if validation_frame.empty:
        rmse = float(training_frame[target_column].std() * 0.15)
    else:
        predictions = model.predict(validation_frame[feature_columns])
        rmse = float(np.sqrt(mean_squared_error(validation_frame[target_column], predictions)))

    full_model = HistGradientBoostingRegressor(random_state=42, max_depth=6, max_iter=150, learning_rate=0.08)
    full_model.fit(training_frame[feature_columns], training_frame[target_column])

    return DepartmentForecastModel(
        target_column=target_column,
        feature_columns=feature_columns,
        model=full_model,
        rmse=max(rmse, 1.5),
        min_observed=float(training_frame[target_column].min()),
        max_observed=float(training_frame[target_column].max()),
    )
