from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
from statsmodels.tsa.holtwinters import ExponentialSmoothing
from statsmodels.tsa.ar_model import AutoReg

WEIGHTS = {"ema_regression": 0.45, "holt_winters": 0.35, "ar3": 0.20}


def rolling_outlier_adjust(series: pd.Series, window: int = 6, threshold: float = 2.5) -> Tuple[pd.Series, List[dict]]:
    values = series.astype(float).copy()
    adjusted = values.copy()
    outliers: List[dict] = []

    for i in range(window, len(values)):
        hist = adjusted.iloc[i - window:i]
        mean = hist.mean()
        std = hist.std(ddof=0)
        if std == 0 or np.isnan(std):
            continue
        z = (values.iloc[i] - mean) / std
        if abs(z) > threshold:
            median = float(hist.median())
            outliers.append(
                {
                    "index": int(i),
                    "date": str(series.index[i].date()),
                    "raw": round(float(values.iloc[i]), 2),
                    "adjusted": round(median, 2),
                    "z_score": round(float(z), 3),
                    "type": "spike" if z > 0 else "dip",
                }
            )
            adjusted.iloc[i] = median

    return adjusted.round(2), outliers


def compute_ema(series: pd.Series, alpha: float = 0.15) -> pd.Series:
    return series.ewm(alpha=alpha, adjust=False).mean().round(2)


def forecast_ema_regression(ema_series: pd.Series, horizon: int = 18) -> Dict[str, List[float] | float]:
    window = min(12, len(ema_series))
    y = ema_series.iloc[-window:].astype(float).to_numpy()
    x = np.arange(window, dtype=float)
    slope, intercept = np.polyfit(x, y, 1)
    fitted = intercept + slope * x
    residuals = y - fitted
    rmse = float(np.sqrt(np.mean(residuals ** 2))) if len(residuals) else 0.0

    future_x = np.arange(window, window + horizon, dtype=float)
    preds = intercept + slope * future_x
    steps = np.arange(1, horizon + 1, dtype=float)
    err80 = 1.28 * rmse * np.sqrt(steps)
    err95 = 1.96 * rmse * np.sqrt(steps)

    return {
        "preds": np.round(preds, 2).tolist(),
        "lo80": np.round(preds - err80, 2).tolist(),
        "hi80": np.round(preds + err80, 2).tolist(),
        "lo95": np.round(preds - err95, 2).tolist(),
        "hi95": np.round(preds + err95, 2).tolist(),
        "slope": round(float(slope), 4),
        "rmse": round(rmse, 4),
    }


def forecast_holt_winters(series: pd.Series, horizon: int = 18, seasonal_periods: int = 12) -> List[float]:
    try:
        model = ExponentialSmoothing(
            series.astype(float),
            trend="add",
            seasonal="mul",
            seasonal_periods=seasonal_periods,
            initialization_method="estimated",
        ).fit(optimized=True, use_brute=True)
        forecast = model.forecast(horizon)
    except Exception:
        model = ExponentialSmoothing(
            series.astype(float),
            trend="add",
            seasonal=None,
            initialization_method="estimated",
        ).fit(optimized=True)
        forecast = model.forecast(horizon)
    return np.round(forecast.to_numpy(), 2).tolist()


def forecast_ar3(series: pd.Series, horizon: int = 18) -> List[float]:
    values = series.astype(float)
    try:
        model = AutoReg(values, lags=3, old_names=False, trend="c").fit()
        pred = model.predict(start=len(values), end=len(values) + horizon - 1, dynamic=False)
        return np.round(np.maximum(pred.to_numpy(), 0), 2).tolist()
    except Exception:
        hist = values.iloc[-3:].tolist()
        coeffs = [0.5, 0.3, 0.2]
        preds = []
        for _ in range(horizon):
            next_v = sum(c * hist[-1 - i] for i, c in enumerate(coeffs))
            next_v = max(next_v, 0)
            preds.append(round(next_v, 2))
            hist.append(next_v)
        return preds


def ensemble_forecast(ema_fc: List[float], hw_fc: List[float], ar_fc: List[float]) -> List[float]:
    ensemble = []
    for a, b, c in zip(ema_fc, hw_fc, ar_fc):
        ensemble.append(round(WEIGHTS["ema_regression"] * a + WEIGHTS["holt_winters"] * b + WEIGHTS["ar3"] * c, 2))
    return ensemble


def holdout_metrics(series: pd.Series, alpha: float = 0.15, holdout: int = 6) -> Dict[str, float]:
    if len(series) <= max(18, holdout + 6):
        return {}

    train = series.iloc[:-holdout]
    test = series.iloc[-holdout:].astype(float).to_numpy()

    adj, _ = rolling_outlier_adjust(train)
    ema = compute_ema(adj, alpha)
    ema_fc = np.array(forecast_ema_regression(ema, holdout)["preds"], dtype=float)
    hw_fc = np.array(forecast_holt_winters(adj, holdout), dtype=float)
    ar_fc = np.array(forecast_ar3(adj, holdout), dtype=float)
    ens_fc = np.array(ensemble_forecast(ema_fc.tolist(), hw_fc.tolist(), ar_fc.tolist()), dtype=float)

    def rmse(pred: np.ndarray) -> float:
        return float(np.sqrt(np.mean((pred - test) ** 2)))

    return {
        "ema_regression_rmse": round(rmse(ema_fc), 3),
        "holt_winters_rmse": round(rmse(hw_fc), 3),
        "ar3_rmse": round(rmse(ar_fc), 3),
        "ensemble_rmse": round(rmse(ens_fc), 3),
    }


@dataclass
class PipelineConfig:
    alpha: float = 0.15
    horizon: int = 18
    outlier_window: int = 6
    outlier_threshold: float = 2.5


def run_pipeline(series: pd.Series, config: PipelineConfig) -> Dict:
    adjusted, outliers = rolling_outlier_adjust(series, config.outlier_window, config.outlier_threshold)
    ema = compute_ema(adjusted, config.alpha)
    ema_fc = forecast_ema_regression(ema, config.horizon)
    hw_fc = forecast_holt_winters(adjusted, config.horizon)
    ar_fc = forecast_ar3(adjusted, config.horizon)
    ensemble = ensemble_forecast(ema_fc["preds"], hw_fc, ar_fc)
    metrics = holdout_metrics(series, config.alpha)

    return {
        "raw": series.round(2).tolist(),
        "adjusted": adjusted.round(2).tolist(),
        "ema": ema.round(2).tolist(),
        "outliers": outliers,
        "ema_forecast": ema_fc,
        "holt_winters_forecast": hw_fc,
        "ar3_forecast": ar_fc,
        "ensemble_forecast": ensemble,
        "weights": WEIGHTS,
        "metrics": metrics,
        "summary": {
            "latest_actual": round(float(series.iloc[-1]), 2),
            "latest_adjusted": round(float(adjusted.iloc[-1]), 2),
            "next_forecast": round(float(ensemble[0]), 2),
            "trend_slope": ema_fc["slope"],
            "outlier_count": len(outliers),
            "series_mean": round(float(adjusted.mean()), 2),
            "series_std": round(float(adjusted.std(ddof=0)), 2),
        },
    }
