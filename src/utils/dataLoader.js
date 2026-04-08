/**
 * CSV loader — parses sales_data.csv into per-category time series.
 * Works in both browser (fetch) and Node.js (fs).
 */

"use strict";

const CATEGORIES = ["prepared_meals", "beverages", "dairy_deli", "snacks_bakery"];

const CATEGORY_LABELS = {
  prepared_meals: "Prepared Meals",
  beverages:      "Beverages",
  dairy_deli:     "Dairy & Deli",
  snacks_bakery:  "Snacks & Bakery",
};

/**
 * Parse raw CSV text → aggregated monthly totals per category.
 * Aggregates across all stores.
 * @param {string} csvText
 * @returns {{ dates: string[], series: Object.<string, number[]>, stores: string[] }}
 */
function parseCSV(csvText) {
  const lines = csvText.trim().split("\n");
  const headers = lines[0].split(",").map(h => h.trim());

  const dateSet   = new Set();
  const storeSet  = new Set();
  const rawRows   = [];

  for (let i = 1; i < lines.length; i++) {
    const vals = lines[i].split(",");
    const row  = {};
    headers.forEach((h, j) => row[h] = vals[j]?.trim());
    dateSet.add(row.date);
    storeSet.add(row.store);
    rawRows.push(row);
  }

  const dates  = [...dateSet].sort();
  const stores = [...storeSet].sort();

  // Aggregate: sum all stores per date per category
  const series = {};
  CATEGORIES.forEach(cat => { series[cat] = Array(dates.length).fill(0); });

  rawRows.forEach(row => {
    const di = dates.indexOf(row.date);
    if (di === -1) return;
    CATEGORIES.forEach(cat => {
      series[cat][di] += parseInt(row[cat] || 0, 10);
    });
  });

  return { dates, series, stores };
}

/**
 * Format a YYYY-MM-DD date string to "Jan '22" display label.
 */
function formatDateLabel(dateStr) {
  const d = new Date(dateStr + "T00:00:00");
  return d.toLocaleString("default", { month: "short" }) + " '" + String(d.getFullYear()).slice(2);
}

/**
 * Generate forward date labels beyond the dataset end.
 * @param {string} lastDate  YYYY-MM-DD
 * @param {number} n         number of future months
 */
function futureLabels(lastDate, n) {
  const labels = [];
  const d = new Date(lastDate + "T00:00:00");
  for (let i = 1; i <= n; i++) {
    const fd = new Date(d.getFullYear(), d.getMonth() + i, 1);
    labels.push(fd.toLocaleString("default", { month: "short" }) + " '" + String(fd.getFullYear()).slice(2));
  }
  return labels;
}

if (typeof module !== "undefined") {
  module.exports = { parseCSV, formatDateLabel, futureLabels, CATEGORIES, CATEGORY_LABELS };
}
