/** Build operational intelligence timeline from existing API data */

export function buildIntelligenceFeed({ anomalies, insights, forecasts, partialErrors, isLive }) {
  const items = [];

  for (const a of anomalies || []) {
    items.push({
      id: `anomaly-${a.id}`,
      type: "anomaly",
      severity: a.severity || "medium",
      titleKey: "timeline.types.anomaly",
      titleFallback: a.anomaly_type?.replace(/_/g, " ") || "Anomaly",
      subtitle: a.airline,
      timestamp: a.detected_at,
      meta: `${a.observed_value} vs ${a.expected_value}`
    });
  }

  for (const ins of insights || []) {
    items.push({
      id: `insight-${ins.id || ins.summary}`,
      type: "insight",
      severity: ins.severity || "neutral",
      titleKey: "timeline.types.insight",
      titleFallback: ins.category || "Insight",
      subtitle: ins.airline,
      timestamp: ins.generated_at,
      meta: (ins.summary || ins.insight_text || "").slice(0, 80)
    });
  }

  const repForecast = (forecasts?.metrics?.reputation_score || []).find((r) => r.horizon === "weekly");
  if (repForecast?.generated_at) {
    items.push({
      id: "forecast-reputation",
      type: "forecast",
      severity: repForecast.trend_direction === "declining" ? "medium" : "low",
      titleKey: "timeline.types.forecast",
      titleFallback: "Reputation forecast",
      subtitle: repForecast.airline || "Portfolio",
      timestamp: repForecast.generated_at,
      meta: `${repForecast.current_value} → ${repForecast.forecast_value}`
    });
  }

  if (partialErrors?.length) {
    items.push({
      id: "crawl-partial",
      type: "crawl",
      severity: "medium",
      titleKey: "timeline.types.partialSync",
      titleFallback: "Partial API sync",
      subtitle: "",
      timestamp: new Date().toISOString(),
      metaKey: "timeline.partialMeta",
      metaParams: { count: partialErrors.length }
    });
  }

  if (!isLive) {
    items.push({
      id: "crawl-demo",
      type: "crawl",
      severity: "low",
      titleKey: "timeline.types.demoMode",
      titleFallback: "Demo mode",
      subtitle: "",
      timestamp: new Date().toISOString(),
      metaKey: "timeline.demoMeta"
    });
  }

  return items
    .filter((i) => i.timestamp)
    .sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp))
    .slice(0, 24);
}
