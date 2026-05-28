import { baseChartTheme, axisStyle, PALANTIR_COLORS } from "./chartTheme";
import { executiveChartBase, executiveXAxis, executiveYAxis } from "./executiveChartTheme";

export function buildRatingOption(timeline, locale = "en") {
  const categories = timeline.map((row) => (row.month || row.period || "").slice(0, 10));
  const values = timeline.map((row) => row.average_rating ?? row.score / 10);
  return {
    ...executiveChartBase(),
    xAxis: executiveXAxis(categories, locale),
    yAxis: executiveYAxis({ min: 0, max: 10, splitNumber: 4 }),
    series: [
      {
        data: values,
        type: "line",
        smooth: 0.35,
        showSymbol: false,
        areaStyle: { color: "rgba(45, 212, 168, 0.06)" },
        lineStyle: { color: PALANTIR_COLORS.positive, width: 2 },
        itemStyle: { color: PALANTIR_COLORS.positive },
      },
    ],
  };
}

export function buildReputationForecastOption(primary, { actualLabel, forecastLabel, insufficient }, locale = "en") {
  const history = primary?.payload?.history || [];
  const projected = primary?.payload?.forecast_points || [];
  const categories = [...history.map((h) => h.period), ...projected.map((p) => p.period)];
  const values = projected.map((p) => p.value).filter((v) => v != null);
  const band = values.length
    ? values.map((v) => [Math.max(0, v - 6), Math.min(100, v + 6)])
    : [];

  return {
    ...executiveChartBase({ grid: { left: 44, right: 12, top: 12, bottom: 28 } }),
    xAxis: executiveXAxis(categories, locale),
    yAxis: executiveYAxis({ min: 0, max: 100, splitNumber: 4 }),
    series: [
      ...(band.length
        ? [
            {
              name: "CI lower",
              type: "line",
              data: [...history.map(() => null), ...band.map((b) => b[0])],
              lineStyle: { opacity: 0 },
              stack: "band",
              symbol: "none",
              areaStyle: { color: "rgba(61, 158, 255, 0.06)" },
            },
            {
              name: "CI upper",
              type: "line",
              data: [...history.map(() => null), ...band.map((b) => b[1] - b[0])],
              lineStyle: { opacity: 0 },
              stack: "band",
              symbol: "none",
              areaStyle: { color: "rgba(61, 158, 255, 0.06)" },
            },
          ]
        : []),
      {
        name: actualLabel,
        type: "line",
        data: [...history.map((h) => h.value), ...projected.map(() => null)],
        smooth: 0.35,
        showSymbol: false,
        lineStyle: { color: PALANTIR_COLORS.positive, width: 2 },
        itemStyle: { color: PALANTIR_COLORS.positive },
        markPoint: insufficient
          ? undefined
          : {
              symbol: "circle",
              symbolSize: 5,
              data: [{ coord: [categories[history.length - 1], history[history.length - 1]?.value] }],
            },
      },
      {
        name: forecastLabel,
        type: "line",
        data: [...history.map(() => null), ...projected.map((p) => p.value)],
        smooth: 0.35,
        showSymbol: false,
        lineStyle: { color: PALANTIR_COLORS.warning, width: 2, type: "dashed" },
        itemStyle: { color: PALANTIR_COLORS.warning },
      },
    ],
  };
}

export function buildSentimentOption(sentiment, translateLabel) {
  return {
    ...baseChartTheme(),
    xAxis: { type: "category", data: sentiment.map((r) => translateLabel(r.label)), ...axisStyle() },
    yAxis: { type: "value", ...axisStyle() },
    series: [
      {
        data: sentiment.map((row) => ({
          value: row.value,
          itemStyle: {
            color: row.label === "negative" ? PALANTIR_COLORS.risk
              : row.label === "positive" ? PALANTIR_COLORS.positive
              : PALANTIR_COLORS.warning
          }
        })),
        type: "bar", barWidth: 24
      }
    ]
  };
}

export function buildHeatmapOption(heatmapAirlines, heatmapTopics, topicHeatmap) {
  return {
    ...baseChartTheme({ grid: { left: 90, right: 20, top: 20, bottom: 60 } }),
    tooltip: { position: "top", backgroundColor: "rgba(10,16,24,0.92)", borderColor: "#2a3d4f" },
    xAxis: { type: "category", data: heatmapTopics, axisLabel: { color: PALANTIR_COLORS.axis, rotate: 30, fontSize: 9 } },
    yAxis: { type: "category", data: heatmapAirlines, axisLabel: { color: PALANTIR_COLORS.axis, fontSize: 9 } },
    visualMap: { min: 0, max: 10, show: false, inRange: { color: ["#14202c", "#d4a332", "#c95545"] } },
    series: [
      {
        type: "heatmap",
        data: heatmapAirlines.flatMap((slug, y) =>
          heatmapTopics.map((topic, x) => {
            const row = (topicHeatmap[slug] || []).find((item) => item.label === topic);
            return [x, y, row ? row.weight : 0];
          })
        )
      }
    ]
  };
}

export function buildComplaintDensityOption(reputation, complaintDensity) {
  return {
    ...baseChartTheme(),
    xAxis: { type: "category", data: reputation.map((r) => r.slug), axisLabel: { color: PALANTIR_COLORS.axis, rotate: 20, fontSize: 9 } },
    yAxis: { type: "value", max: 100, ...axisStyle() },
    series: [
      {
        type: "bar",
        data: reputation.map((r) => complaintDensity?.[r.slug] ?? r.complaint_density ?? 0),
        itemStyle: {
          color: {
            type: "linear", x: 0, y: 0, x2: 0, y2: 1,
            colorStops: [
              { offset: 0, color: PALANTIR_COLORS.risk },
              { offset: 1, color: "rgba(201, 85, 69, 0.25)" }
            ]
          }
        }
      }
    ]
  };
}

export function exportReputationCsv(reputation, complaintDensity) {
  const rows = [
    ["airline", "score", "reviews", "complaint_density"],
    ...reputation.map((row) => [
      row.airline, row.score, row.review_count,
      complaintDensity?.[row.slug] ?? row.complaint_density
    ])
  ];
  const csv = rows.map((r) => r.join(",")).join("\n");
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = "skytrax-reputation.csv";
  link.click();
  URL.revokeObjectURL(url);
}
