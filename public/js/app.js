"use strict";

const COLORS = {
  actual: "#2f6fed",
  adjusted: "#1f9d8b",
  ema: "#d9822b",
  ensemble: "#7c5cff",
  band: "rgba(124, 92, 255, 0.12)",
  grid: "rgba(16, 42, 67, 0.08)",
  tick: "#52606d",
};

const STATE = {
  data: null,
  store: null,
  category: null,
  horizon: 12,
  view: "ensemble",
  charts: {},
};

window.addEventListener("DOMContentLoaded", async () => {
  await loadPayload();
  wireControls();
  render();
});

async function loadPayload() {
  const resp = await fetch("data/forecast_data.json");
  STATE.data = await resp.json();
  const meta = STATE.data.meta;
  STATE.store = meta.default_store;
  STATE.category = meta.default_category;

  const storeSelect = document.getElementById("store-select");
  storeSelect.innerHTML = meta.stores.map(v => `<option value="${v}">${v}</option>`).join("");

  const categorySelect = document.getElementById("category-select");
  categorySelect.innerHTML = meta.categories.map(v => `<option value="${v}">${meta.category_labels[v]}</option>`).join("");

  document.getElementById("toolbar-note").textContent =
    `${meta.rows.toLocaleString()} rows loaded · ${meta.history_points} monthly periods · α=${meta.config.alpha} · outlier window=${meta.config.outlier_window}`;
}

function wireControls() {
  document.getElementById("store-select").addEventListener("change", e => {
    STATE.store = e.target.value;
    render();
  });
  document.getElementById("category-select").addEventListener("change", e => {
    STATE.category = e.target.value;
    render();
  });
  document.getElementById("horizon-select").addEventListener("change", e => {
    STATE.horizon = Number(e.target.value);
    render();
  });
  document.getElementById("view-select").addEventListener("change", e => {
    STATE.view = e.target.value;
    render();
  });
}

function activePipeline() {
  return STATE.data.pipelines[STATE.store][STATE.category];
}

function categoryLabel() {
  return STATE.data.meta.category_labels[STATE.category];
}

function render() {
  renderKPIs();
  renderHistoryChart();
  renderModelChart();
  renderWeights();
  renderOutliers();
  document.getElementById("series-badge").textContent = `${STATE.store} · ${categoryLabel()}`;
}

function renderKPIs() {
  const p = activePipeline();
  const delta = ((p.summary.next_forecast - p.summary.latest_adjusted) / p.summary.latest_adjusted) * 100;
  const trendText = p.summary.trend_slope >= 0 ? "Rising" : "Falling";
  const cards = [
    ["Latest actual", formatNumber(p.summary.latest_actual), "Raw final observation"],
    ["Latest adjusted", formatNumber(p.summary.latest_adjusted), "After outlier cleanup"],
    ["Next forecast", formatNumber(p.summary.next_forecast), `${delta >= 0 ? "+" : ""}${delta.toFixed(1)}% vs latest adjusted`],
    ["Trend slope", p.summary.trend_slope.toFixed(2), `${trendText} EMA regression trend`],
    ["Outliers", String(p.summary.outlier_count), `${STATE.data.meta.config.outlier_threshold}σ threshold`],
  ];

  document.getElementById("kpi-grid").innerHTML = cards.map(([label, value, sub]) => `
    <div class="kpi">
      <div class="kpi-label">${label}</div>
      <div class="kpi-value">${value}</div>
      <div class="kpi-sub">${sub}</div>
    </div>
  `).join("");
}

function renderHistoryChart() {
  destroyChart("history");
  const p = activePipeline();
  const labels = [...STATE.data.labels, ...STATE.data.future_labels.slice(0, STATE.horizon)];
  const nullPad = Array(STATE.horizon).fill(null);
  const historyPad = Array(STATE.data.labels.length - 1).fill(null);
  const forecastSeries = selectForecastSeries(p);
  const lo80 = p.ema_forecast.lo80.slice(0, STATE.horizon);
  const hi80 = p.ema_forecast.hi80.slice(0, STATE.horizon);

  const datasets = [
    lineDataset("Actual", [...p.raw, ...nullPad], COLORS.actual),
    lineDataset("Adjusted", [...p.adjusted, ...nullPad], COLORS.adjusted),
    lineDataset("EMA", [...p.ema, ...nullPad], COLORS.ema),
    {
      label: "80% lower band",
      data: [...historyPad, p.adjusted[p.adjusted.length - 1], ...lo80],
      borderColor: "rgba(124, 92, 255, 0)",
      pointRadius: 0,
      tension: 0.25,
    },
    {
      label: "80% upper band",
      data: [...historyPad, p.adjusted[p.adjusted.length - 1], ...hi80],
      borderColor: "rgba(124, 92, 255, 0)",
      backgroundColor: COLORS.band,
      pointRadius: 0,
      fill: "-1",
      tension: 0.25,
    },
    {
      label: `${viewName()} forecast`,
      data: [...historyPad, p.adjusted[p.adjusted.length - 1], ...forecastSeries],
      borderColor: COLORS.ensemble,
      backgroundColor: COLORS.ensemble,
      borderWidth: 2.5,
      pointRadius: 0,
      borderDash: [6, 4],
      tension: 0.25,
    },
  ];

  STATE.charts.history = new Chart(document.getElementById("history-chart"), {
    type: "line",
    data: { labels, datasets },
    options: baseOptions({ legend: true }),
  });
}

function renderModelChart() {
  destroyChart("model");
  const p = activePipeline();
  const labels = STATE.data.future_labels.slice(0, STATE.horizon);
  STATE.charts.model = new Chart(document.getElementById("model-chart"), {
    type: "line",
    data: {
      labels,
      datasets: [
        lineDataset("EMA regression", p.ema_forecast.preds.slice(0, STATE.horizon), COLORS.ema),
        lineDataset("Holt-Winters", p.holt_winters_forecast.slice(0, STATE.horizon), COLORS.adjusted),
        lineDataset("AR(3)", p.ar3_forecast.slice(0, STATE.horizon), COLORS.actual),
        lineDataset("Ensemble", p.ensemble_forecast.slice(0, STATE.horizon), COLORS.ensemble, 2.5),
      ],
    },
    options: baseOptions({ legend: true }),
  });
}

function renderWeights() {
  const p = activePipeline();
  const colors = {
    ema_regression: COLORS.ema,
    holt_winters: COLORS.adjusted,
    ar3: COLORS.actual,
  };
  document.getElementById("weights").innerHTML = Object.entries(p.weights).map(([key, value]) => `
    <div class="weight-row">
      <div class="weight-top"><span>${humanize(key)}</span><strong>${(value * 100).toFixed(0)}%</strong></div>
      <div class="weight-bar"><div class="weight-fill" style="width:${value * 100}%;background:${colors[key]}"></div></div>
    </div>
  `).join("");

  const metrics = p.metrics || {};
  const metricKeys = Object.keys(metrics);
  document.getElementById("metrics").innerHTML = metricKeys.length
    ? metricKeys.map(key => `<div class="metric-item"><span>${humanize(key)}</span><strong>${metrics[key].toFixed(2)}</strong></div>`).join("")
    : `<div class="empty-state">Not enough history to calculate holdout metrics.</div>`;
}

function renderOutliers() {
  const outliers = activePipeline().outliers || [];
  const body = document.getElementById("outlier-body");
  if (!outliers.length) {
    body.innerHTML = `<tr><td colspan="5" class="empty-state">No outliers flagged for this series.</td></tr>`;
    return;
  }
  body.innerHTML = outliers.map(o => `
    <tr>
      <td>${o.date}</td>
      <td><span class="badge ${o.type}">${o.type}</span></td>
      <td>${formatNumber(o.raw)}</td>
      <td>${formatNumber(o.adjusted)}</td>
      <td>${o.z_score.toFixed(3)}</td>
    </tr>
  `).join("");
}

function lineDataset(label, data, color, width = 2) {
  return {
    label,
    data,
    borderColor: color,
    backgroundColor: color,
    borderWidth: width,
    pointRadius: 0,
    tension: 0.25,
  };
}

function selectForecastSeries(p) {
  if (STATE.view === "ema") return p.ema_forecast.preds.slice(0, STATE.horizon);
  if (STATE.view === "holt") return p.holt_winters_forecast.slice(0, STATE.horizon);
  if (STATE.view === "ar3") return p.ar3_forecast.slice(0, STATE.horizon);
  return p.ensemble_forecast.slice(0, STATE.horizon);
}

function viewName() {
  return {
    ensemble: "Ensemble",
    ema: "EMA regression",
    holt: "Holt-Winters",
    ar3: "AR(3)",
  }[STATE.view];
}

function humanize(key) {
  return key.replaceAll("_", " ").replace(/\brmse\b/i, "RMSE").replace(/\bar3\b/i, "AR(3)").replace(/\bema\b/i, "EMA").replace(/\bholt winters\b/i, "Holt-Winters").replace(/\bregression\b/i, "Regression").replace(/(^|\s)\S/g, m => m.toUpperCase());
}

function formatNumber(v) {
  return Number(v).toLocaleString(undefined, { maximumFractionDigits: 1 });
}

function destroyChart(key) {
  if (STATE.charts[key]) {
    STATE.charts[key].destroy();
    delete STATE.charts[key];
  }
}

function baseOptions({ legend = false } = {}) {
  return {
    responsive: true,
    maintainAspectRatio: false,
    interaction: { mode: "index", intersect: false },
    plugins: {
      legend: { display: legend, position: "bottom", labels: { boxWidth: 10, color: COLORS.tick, usePointStyle: true } },
      tooltip: {
        backgroundColor: "#102a43",
        titleColor: "#fff",
        bodyColor: "#d9e2ec",
        padding: 10,
        callbacks: {
          label: ctx => `${ctx.dataset.label}: ${formatNumber(ctx.parsed.y)}`,
        },
      },
    },
    scales: {
      x: {
        grid: { display: false },
        ticks: { color: COLORS.tick, maxRotation: 0, autoSkip: true, maxTicksLimit: 10 },
      },
      y: {
        grid: { color: COLORS.grid },
        ticks: { color: COLORS.tick },
      },
    },
  };
}
