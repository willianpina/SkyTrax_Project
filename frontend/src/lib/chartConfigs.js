import { baseChartTheme, axisStyle, PALANTIR_COLORS } from "./chartTheme";

export function buildRatingOption(timeline) {
  const categories = timeline.map((row) => (row.month || "").slice(0, 7));
  const values = timeline.map((row) => row.average_rating ?? row.score / 10);
  return {
    ...baseChartTheme(),
    xAxis: { type: "category", data: categories, ...axisStyle() },
    yAxis: { type: "value", min: 0, max: 10, ...axisStyle() },
    series: [
      {
        data: values, type: "line", smooth: true,
        areaStyle: { color: "rgba(45, 212, 168, 0.1)" },
        lineStyle: { color: PALANTIR_COLORS.positive, width: 2 },
        itemStyle: { color: PALANTIR_COLORS.positive }
      }
    ]
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
