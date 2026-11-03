from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class DataQuality:
    input_rows: int
    output_rows: int
    invalid_date_rows: int
    invalid_well_rows: int
    invalid_value_rows: int
    aggregated_duplicate_rows: int


def prepare_production_data(
    frame: pd.DataFrame,
    date_column: str,
    well_column: str,
    value_column: str,
    aggregation: str = "sum",
) -> tuple[pd.DataFrame, DataQuality]:
    """Select, clean, and aggregate one production measure by well and date."""
    if aggregation not in {"sum", "mean"}:
        raise ValueError("Aggregation must be 'sum' or 'mean'.")
    for column in (date_column, well_column, value_column):
        if column not in frame.columns:
            raise ValueError(f"Column not found: {column}")

    selected = frame[[date_column, well_column, value_column]].copy()
    dates = pd.to_datetime(selected[date_column], errors="coerce")
    wells = selected[well_column].astype("string").str.strip()
    values = pd.to_numeric(selected[value_column], errors="coerce")
    invalid_dates = int(dates.isna().sum())
    invalid_wells = int((wells.isna() | wells.eq("")).sum())
    invalid_values = int(values.isna().sum())

    clean = pd.DataFrame({"date": dates, "well": wells, "production": values})
    clean = clean.dropna(subset=["date", "well", "production"])
    clean = clean[clean["well"].ne("")]
    before_aggregation = len(clean)
    clean = (
        clean.groupby(["date", "well"], as_index=False, sort=True)["production"]
        .agg(aggregation)
        .sort_values(["date", "well"])
        .reset_index(drop=True)
    )
    quality = DataQuality(
        input_rows=len(frame),
        output_rows=len(clean),
        invalid_date_rows=invalid_dates,
        invalid_well_rows=invalid_wells,
        invalid_value_rows=invalid_values,
        aggregated_duplicate_rows=before_aggregation - len(clean),
    )
    if clean.empty:
        raise ValueError("No valid rows remain after parsing the selected columns.")
    return clean, quality


def forecast_well(history: pd.DataFrame, periods: int) -> pd.DataFrame:
    """Fit a small linear trend to recent observations and project future periods."""
    if periods < 1:
        raise ValueError("Forecast periods must be at least 1.")
    series = history.sort_values("date").tail(90).reset_index(drop=True)
    if series.empty:
        raise ValueError("The selected well has no production observations.")

    y = series["production"].astype(float).to_numpy()
    x = pd.Series(range(len(y)), dtype="float64").to_numpy()
    if len(y) > 1:
        slope, intercept = np.polyfit(x, y, 1)
    else:
        slope, intercept = 0.0, float(y[0])

    last_date = pd.Timestamp(series["date"].iloc[-1])
    date_deltas = series["date"].sort_values().drop_duplicates().diff().dropna()
    cadence = date_deltas.median() if not date_deltas.empty else pd.Timedelta(days=1)
    if pd.isna(cadence) or cadence <= pd.Timedelta(0):
        cadence = pd.Timedelta(days=1)

    future_x = range(len(y), len(y) + periods)
    predictions = [max(0.0, float(intercept + slope * step)) for step in future_x]
    return pd.DataFrame({
        "date": [last_date + cadence * step for step in range(1, periods + 1)],
        "forecast": predictions,
    })


def flag_anomalies(data: pd.DataFrame, threshold: float = 3.5) -> pd.DataFrame:
    """Flag unusual deviations from each well's centered rolling median."""
    pieces: list[pd.DataFrame] = []
    for _, group in data.groupby("well", sort=False):
        group = group.sort_values("date").copy()
        values = group["production"].astype(float)
        baseline = values.rolling(window=7, center=True, min_periods=3).median()
        residual = (values - baseline).abs()
        rolling_mad = residual.rolling(window=7, center=True, min_periods=3).median()
        score = 0.6745 * residual / rolling_mad.where(rolling_mad.ne(0))
        zero_mad = rolling_mad.eq(0) & residual.gt(0)
        group["rolling_baseline"] = baseline
        group["anomaly_score"] = score.fillna(0).where(~zero_mad, float("inf"))
        group["is_anomaly"] = group["anomaly_score"].gt(threshold)
        pieces.append(group)
    if not pieces:
        return data.assign(rolling_baseline=pd.NA, anomaly_score=0.0, is_anomaly=False)
    return pd.concat(pieces, ignore_index=True).sort_values(["date", "well"]).reset_index(drop=True)
