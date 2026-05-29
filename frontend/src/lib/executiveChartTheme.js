import { baseChartTheme, axisStyle, PALANTIR_COLORS } from "./chartTheme";

/** Compact period labels for executive charts (e.g. Mar '25). */
export function formatChartAxisLabel(value, locale = "en") {
  if (value == null || value === "") return "";
  const raw = String(value).trim();
  const iso = raw.length >= 7 ? raw.slice(0, 10) : raw;
  const d = new Date(iso.includes("T") ? iso : `${iso}T12:00:00`);
  if (Number.isNaN(d.getTime())) return raw.slice(0, 7);
  const loc = locale === "pt" || locale?.startsWith?.("pt") ? "pt-BR" : "en-US";
  return d.toLocaleDateString(loc, { month: "short", year: "2-digit" });
}

/** Show first, last, and ~4 interior ticks — avoids X-axis clutter. */
export function sparseAxisInterval(total) {
  return (index) => {
    if (total <= 6) return true;
    if (index === 0 || index === total - 1) return true;
    const step = Math.max(1, Math.floor(total / 4));
    return index % step === 0;
  };
}

const EXEC_GRID = { left: 40, right: 12, top: 16, bottom: 28, containLabel: true };

const EXEC_AXIS_LABEL = {
  ...axisStyle().axisLabel,
  fontSize: 9,
  color: "rgba(148, 163, 184, 0.65)",
  margin: 10,
};

const EXEC_SPLIT = {
  show: true,
  lineStyle: { color: "rgba(148, 163, 184, 0.06)", type: "solid" },
};

export function executiveXAxis(categories, locale = "en") {
  const total = categories.length;
  return {
    type: "category",
    data: categories,
    boundaryGap: false,
    axisLine: { show: false },
    axisTick: { show: false },
    axisLabel: {
      ...EXEC_AXIS_LABEL,
      interval: sparseAxisInterval(total),
      formatter: (v) => formatChartAxisLabel(v, locale),
    },
  };
}

export function executiveYAxis({ min, max, splitNumber = 4 } = {}) {
  return {
    type: "value",
    min,
    max,
    splitNumber,
    axisLine: { show: false },
    axisTick: { show: false },
    axisLabel: { ...EXEC_AXIS_LABEL, fontSize: 9 },
    splitLine: EXEC_SPLIT,
  };
}

export function executiveChartBase(overrides = {}) {
  return {
    ...baseChartTheme({ grid: { ...EXEC_GRID, ...overrides.grid } }),
    legend: { show: false },
    ...overrides,
  };
}

export { PALANTIR_COLORS, EXEC_GRID };
