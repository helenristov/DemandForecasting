# Meridian Foods Forecast Studio

Meridian Foods Forecast Studio is a lightweight demand forecasting application for a hypothetical regional food chain. It keeps the project simple by avoiding an API layer for now.

The modeling step now runs in Python using stronger statistical packages, while the front end remains a static dashboard that can be served from any basic local web server.

## What changed

The original browser-side custom forecasting logic has been upgraded to a Python modeling pipeline that preserves the same overall method family:

- Rolling z-score outlier detection with median replacement
- Exponential moving average smoothing
- EMA regression forecast with confidence bands
- Holt-Winters forecasting using `statsmodels`
- AR(3) forecasting using `statsmodels`
- Weighted ensemble forecast

The front end has also been rebuilt into a cleaner, more functional dashboard with:

- Store selector
- Category selector
- Horizon selector
- Model view selector
- KPI cards
- Forecast comparison chart
- Outlier table
- Weighting and holdout RMSE panel

## Architecture

This version intentionally keeps things simple.

1. `data/generate_data.py` creates or refreshes the sample CSV.
2. `scripts/build_forecast_data.py` reads the CSV, runs the Python forecasting pipeline, and writes a JSON payload.
3. `public/index.html` loads that JSON and renders the dashboard in the browser.

There is no backend API required.

## Project structure

```text
meridian-demand-forecast/
├── data/
│   ├── generate_data.py
│   └── sales_data.csv
├── public/
│   ├── data/
│   │   └── forecast_data.json
│   ├── css/
│   │   └── app.css
│   ├── js/
│   │   └── app.js
│   └── index.html
├── scripts/
│   └── build_forecast_data.py
├── src/
│   ├── models/
│   │   └── ensemble.js
│   ├── python_models/
│   │   └── forecasting.py
│   └── utils/
│       └── dataLoader.js
├── requirements.txt
└── README.md
```

## Install

```bash
pip install -r requirements.txt
```

## Run locally

From the repo root:

```bash
python data/generate_data.py
python scripts/build_forecast_data.py
python -m http.server 8080
```

Then open:

```text
http://localhost:8080/public/index.html
```

## Notes

- The dashboard is static and easy to host.
- The Python builder precomputes forecasts for all stores and categories.
- Forecast horizons in the UI are slices of the precomputed 18 month output.
- This keeps the app simple today while leaving room for an API later.

## Future improvements

- Add a FastAPI layer for on-demand forecasting
- Add configurable alpha and outlier thresholds from the UI
- Add file upload support for real datasets
- Add backtesting visualisations and model diagnostics

## License

MIT
