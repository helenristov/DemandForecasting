from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from src.python_models.forecasting import PipelineConfig, run_pipeline

DATA_PATH = BASE_DIR / "data" / "sales_data.csv"
OUTPUT_PATH = BASE_DIR / "public" / "data" / "forecast_data.json"
CATEGORIES = ["prepared_meals", "beverages", "dairy_deli", "snacks_bakery"]
CATEGORY_LABELS = {
    "prepared_meals": "Prepared Meals",
    "beverages": "Beverages",
    "dairy_deli": "Dairy & Deli",
    "snacks_bakery": "Snacks & Bakery",
}


def month_label(dt: pd.Timestamp) -> str:
    return dt.strftime("%b %y")


def future_labels(last_date: pd.Timestamp, horizon: int) -> list[str]:
    dates = pd.date_range(last_date + pd.offsets.MonthBegin(1), periods=horizon, freq="MS")
    return [month_label(d) for d in dates]


def build_series(df: pd.DataFrame) -> dict:
    stores = sorted(df["store"].unique().tolist())
    store_options = ["All Stores"] + stores
    result = {}

    for store in store_options:
        frame = df if store == "All Stores" else df[df["store"] == store]
        grouped = frame.groupby("date")[CATEGORIES].sum().sort_index()
        result[store] = {}
        for category in CATEGORIES:
            result[store][category] = grouped[category].tolist()
    return result, store_options


def main() -> None:
    df = pd.read_csv(DATA_PATH, parse_dates=["date"]).sort_values(["date", "store"])
    config = PipelineConfig(alpha=0.15, horizon=18, outlier_window=6, outlier_threshold=2.5)

    stores = sorted(df["store"].unique().tolist())
    store_options = ["All Stores"] + stores
    grouped_all = df.groupby("date")[CATEGORIES].sum().sort_index()
    labels = [month_label(d) for d in grouped_all.index]
    future = future_labels(grouped_all.index.max(), config.horizon)

    pipelines = {}
    for store in store_options:
        frame = grouped_all if store == "All Stores" else df[df["store"] == store].groupby("date")[CATEGORIES].sum().sort_index()
        pipelines[store] = {}
        for category in CATEGORIES:
            series = frame[category]
            pipelines[store][category] = run_pipeline(series, config)

    payload = {
        "meta": {
            "title": "Meridian Foods Demand Forecasting Dashboard",
            "generated_at": pd.Timestamp.utcnow().isoformat(),
            "rows": int(len(df)),
            "history_points": int(len(labels)),
            "stores": store_options,
            "categories": CATEGORIES,
            "category_labels": CATEGORY_LABELS,
            "default_store": "All Stores",
            "default_category": "prepared_meals",
            "config": {
                "alpha": config.alpha,
                "max_horizon": config.horizon,
                "outlier_window": config.outlier_window,
                "outlier_threshold": config.outlier_threshold,
            },
        },
        "labels": labels,
        "future_labels": future,
        "pipelines": pipelines,
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Wrote forecast dashboard payload → {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
