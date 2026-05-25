/** Enterprise ECharts theme — Palantir Gotham operational intelligence */

export const PALANTIR_COLORS = {
  signal: "#3d9eff",
  positive: "#2dd4a8",
  warning: "#d4a332",
  risk: "#c95545",
  critical: "#e06050",
  muted: "#5a6d7e",
  grid: "#1a2838",
  axis: "#4f6275",
  glass: "rgba(15, 20, 28, 0.72)"
};

export function baseChartTheme(overrides = {}) {
  return {
    backgroundColor: "transparent",
    textStyle: { color: "#b0bec5", fontFamily: "Inter, ui-sans-serif, system-ui, sans-serif", fontSize: 10 },
    grid: { left: 44, right: 16, top: 32, bottom: 36, containLabel: true, ...overrides.grid },
    tooltip: {
      trigger: "axis",
      backgroundColor: "rgba(10, 16, 24, 0.94)",
      borderColor: "#1e2d3d",
      borderWidth: 1,
      textStyle: { color: "#dce4ec", fontSize: 11 },
      extraCssText: "backdrop-filter: blur(8px); box-shadow: 0 4px 16px rgba(0,0,0,0.4);"
    },
    ...overrides
  };
}

export function axisStyle() {
  return {
    axisLine: { lineStyle: { color: "#1e2d3d" } },
    axisLabel: { color: PALANTIR_COLORS.axis, fontSize: 9 },
    splitLine: { lineStyle: { color: PALANTIR_COLORS.grid, type: "dashed" } }
  };
}

export function confidenceBandSeries(categories, lower, upper, name = "CI") {
  return {
    name,
    type: "line",
    data: lower,
    lineStyle: { opacity: 0 },
    stack: "confidence",
    symbol: "none",
    areaStyle: { color: "rgba(61, 158, 255, 0.08)" }
  };
}

export function markAnomalyPoints(categories, anomalies, valueKey = "observed_value") {
  const data = categories.map((cat) => {
    const hit = anomalies.find((a) => (a.detected_at || "").slice(0, 10) === cat);
    return hit ? hit[valueKey] : null;
  });
  return {
    type: "scatter",
    symbol: "pin",
    symbolSize: 24,
    itemStyle: { color: PALANTIR_COLORS.critical },
    data: data.map((v, i) => (v != null ? [i, v] : null)).filter(Boolean),
    z: 10
  };
}
