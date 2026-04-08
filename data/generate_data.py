"""
Sample dataset generator for Regional Food Chain Demand Forecasting
Generates 36 months of historical sales data across 4 product categories
with realistic trends, seasonality, noise, and injected outliers.
"""

import csv
import math
import random
from datetime import date

random.seed(42)

CATEGORIES = [
    {"name": "prepared_meals",  "base": 520, "trend": 3.2, "season_amp": 60, "noise": 40},
    {"name": "beverages",       "base": 310, "trend": 2.1, "season_amp": 35, "noise": 25},
    {"name": "dairy_deli",      "base": 420, "trend": 1.8, "season_amp": 50, "noise": 30},
    {"name": "snacks_bakery",   "base": 280, "trend": 2.8, "season_amp": 40, "noise": 35},
]

STORES = ["North Shore", "Westfield", "Lakeside", "Downtown", "Southgate"]

OUTLIERS = {
    # (category_index, month_index): override_value
    (0,  8):  720,
    (0, 22):  290,
    (1,  5):  450,
    (1, 19):  180,
    (2, 14):  680,
    (2, 27):  210,
    (3,  3):  460,
    (3, 31):  140,
}

START_YEAR, START_MONTH = 2022, 1
N_MONTHS = 36


def gen_value(cat, month_idx):
    t = cat["trend"] * month_idx
    s = cat["season_amp"] * math.sin(2 * math.pi * month_idx / 12 + 1.0)
    n = (random.random() - 0.5) * cat["noise"]
    return round(cat["base"] + t + s + n)


def get_date(month_idx):
    total_month = START_MONTH - 1 + month_idx
    year  = START_YEAR + total_month // 12
    month = total_month % 12 + 1
    return date(year, month, 1)


rows = []
for store in STORES:
    store_seed = sum(ord(c) for c in store)
    for month_idx in range(N_MONTHS):
        dt = get_date(month_idx)
        row = {
            "date":       dt.strftime("%Y-%m-%d"),
            "year":       dt.year,
            "month":      dt.month,
            "store":      store,
        }
        for ci, cat in enumerate(CATEGORIES):
            key = (ci, month_idx)
            if key in OUTLIERS and store == "North Shore":
                val = OUTLIERS[key]
            else:
                random.seed(store_seed * 1000 + ci * 100 + month_idx)
                val = gen_value(cat, month_idx)
            row[cat["name"]] = val
        rows.append(row)

fieldnames = ["date","year","month","store"] + [c["name"] for c in CATEGORIES]
output_path = "data/sales_data.csv"
with open(output_path, "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)

print(f"Generated {len(rows)} rows → {output_path}")
