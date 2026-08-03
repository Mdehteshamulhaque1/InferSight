"""Forecasting engine.

Three methods are supported:

* ``linear``  — ordinary least-squares extrapolation of the trend line.
* ``es``      — single exponential smoothing (level only), alpha tuned by
                grid search over the historical MAPE.
* ``holt``    — Holt's double exponential smoothing (level + trend), the
                recommended default when the series has a clear trend.

The selected model is validated against a trailing holdout slice (last 20%),
reporting MAPE / MAE / RMSE. Forecasts carry growing confidence intervals
(± 1.96 * residual std * sqrt(step)) so uncertainty widens over the horizon.
"""

from __future__ import annotations

import math

from app.schemas.forecast import ForecastMetrics, ForecastPoint, ForecastResponse
from app.utils.time import add_period


class ForecastError(Exception):
    pass


def _linear_coeffs(values: list[float]) -> tuple[float, float]:
    n = len(values)
    xs = list(range(n))
    mean_x = sum(xs) / n
    mean_y = sum(values) / n
    s_xx = sum((x - mean_x) ** 2 for x in xs)
    s_xy = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, values))
    slope = s_xy / s_xx if s_xx else 0.0
    intercept = mean_y - slope * mean_x
    return slope, intercept


def _single_exp_smooth(values: list[float], alpha: float) -> list[float]:
    if not values:
        return []
    smoothed = [values[0]]
    for v in values[1:]:
        smoothed.append(alpha * v + (1 - alpha) * smoothed[-1])
    return smoothed


def _holt(values: list[float], alpha: float, beta: float) -> tuple[list[float], float, float]:
    if not values:
        return [], 0.0, 0.0
    level = values[0]
    trend = values[1] - values[0] if len(values) > 1 else 0.0
    fitted = [level]
    for v in values[1:]:
        prev_level = level
        level = alpha * v + (1 - alpha) * (level + trend)
        trend = beta * (level - prev_level) + (1 - beta) * trend
        fitted.append(level)
    return fitted, level, trend


def _tune_alpha(values: list[float]) -> float:
    best_alpha, best_mape = 0.5, float("inf")
    for alpha in (a / 10 for a in range(1, 10)):
        smoothed = _single_exp_smooth(values, alpha)
        mape = _mape(values[1:], smoothed[1:])
        if mape < best_mape:
            best_alpha, best_mape = alpha, mape
    return best_alpha


def _mape(actual: list[float], predicted: list[float]) -> float | None:
    pairs = [(a, p) for a, p in zip(actual, predicted) if a != 0]
    if not pairs:
        return None
    return sum(abs(a - p) / abs(a) for a, p in pairs) / len(pairs) * 100.0


def _holdout_metrics(values: list[float], predict_fn) -> ForecastMetrics:
    n = len(values)
    if n < 8:
        return ForecastMetrics(method="", holdout_points=0)
    holdout = max(2, n // 5)
    train = values[: n - holdout]
    forecast = predict_fn(train, holdout)
    actual = values[n - holdout :]

    mape = _mape(actual, forecast)
    mae = sum(abs(a - p) for a, p in zip(actual, forecast)) / holdout
    rmse = math.sqrt(sum((a - p) ** 2 for a, p in zip(actual, forecast)) / holdout)
    return ForecastMetrics(
        method="",
        mape=round(mape, 4) if mape is not None else None,
        mae=round(mae, 4),
        rmse=round(rmse, 4),
        holdout_points=holdout,
    )


def _residual_std(values: list[float], fitted: list[float]) -> float:
    pairs = [(a, p) for a, p in zip(values, fitted)]
    if not pairs:
        return 0.0
    mean_res = sum(a - p for a, p in pairs) / len(pairs)
    variance = sum(((a - p) - mean_res) ** 2 for a, p in pairs) / len(pairs)
    return math.sqrt(variance)


def forecast(
    points: list[object],
    horizon: int = 30,
    method: str = "auto",
    granularity: str = "day",
) -> ForecastResponse:
    if not points:
        raise ForecastError("no data points available to forecast")
    if horizon < 1 or horizon > 365:
        raise ForecastError("horizon must be between 1 and 365")
    if len(points) < 3:
        raise ForecastError("at least 3 data points are required to forecast")

    values = [p.value for p in points]
    last_ts = points[-1].timestamp
    n = len(values)

    methods = {"linear", "es", "holt", "auto"}
    if method not in methods:
        raise ForecastError(f"method must be one of {sorted(methods)}")

    # Holdout validation against the chosen model before forecasting.
    def holdout_predict(train: list[float], steps: int) -> list[float]:
        if method == "linear":
            slope, intercept = _linear_coeffs(train)
            return [intercept + slope * (len(train) + i) for i in range(steps)]
        if method == "es":
            alpha = _tune_alpha(train)
            last_level = _single_exp_smooth(train, alpha)[-1]
            return [last_level] * steps
        if method == "holt":
            _, level, trend = _holt(train, 0.5, 0.3)
            return [level + trend * (i + 1) for i in range(steps)]
        # auto
        slope, _ = _linear_coeffs(train)
        mean = sum(train) / len(train)
        if abs(slope) > abs(mean) * 0.02:
            _, level, trend = _holt(train, 0.5, 0.3)
            return [level + trend * (i + 1) for i in range(steps)]
        alpha = _tune_alpha(train)
        last_level = _single_exp_smooth(train, alpha)[-1]
        return [last_level] * steps

    metrics = _holdout_metrics(values, holdout_predict)

    # Full-series fit for projection.
    if method == "linear":
        slope, intercept = _linear_coeffs(values)
        fitted = [intercept + slope * i for i in range(n)]
        projected = [intercept + slope * (n + i) for i in range(horizon)]
        used_method = "linear"
    elif method == "es":
        alpha = _tune_alpha(values)
        fitted = _single_exp_smooth(values, alpha)
        last_level = fitted[-1]
        projected = [last_level] * horizon
        used_method = "es"
    elif method == "holt":
        fitted, level, trend = _holt(values, 0.5, 0.3)
        projected = [level + trend * (i + 1) for i in range(horizon)]
        used_method = "holt"
    else:
        slope, _ = _linear_coeffs(values)
        mean = sum(values) / len(values)
        if abs(slope) > abs(mean) * 0.02:
            fitted, level, trend = _holt(values, 0.5, 0.3)
            projected = [level + trend * (i + 1) for i in range(horizon)]
            used_method = "holt"
        else:
            alpha = _tune_alpha(values)
            fitted = _single_exp_smooth(values, alpha)
            last_level = fitted[-1]
            projected = [last_level] * horizon
            used_method = "es"

    resid_std = _residual_std(values, fitted)
    points_out: list[ForecastPoint] = []
    for i, value in enumerate(projected, start=1):
        ts = add_period(last_ts, granularity, i)
        error = 1.96 * resid_std * math.sqrt(i)
        points_out.append(
            ForecastPoint(
                timestamp=ts,
                value=round(value, 6),
                lower=round(value - error, 6),
                upper=round(value + error, 6),
            )
        )

    metrics.method = used_method
    return ForecastResponse(
        dataset_id=points[0].dataset_id if points else 0,
        horizon=horizon,
        method=used_method,
        seasonality=False,
        metrics=metrics,
        points=points_out,
    )
