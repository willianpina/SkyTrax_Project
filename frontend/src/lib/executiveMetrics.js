/** Client-side executive metrics derived from existing API payloads */

export function computeExecutiveMetrics({ data, reputation, benchmarking, alerts, anomalies }) {
  const rep = Array.isArray(reputation) ? reputation : [];
  const negDist = data?.sentiment_distribution || {};
  const negTotal = (negDist.negative || 0) + (negDist.neutral || 0) + (negDist.positive || 0) || 1;
  const negativeShare = (negDist.negative || 0) / negTotal;

  const avgComplaint =
    rep.length > 0
      ? rep.reduce((s, r) => s + (benchmarking?.complaint_density?.[r.slug] ?? r.complaint_density ?? 0), 0) / rep.length
      : 0;

  const riskEntries = Object.entries(benchmarking?.operational_risk || {});
  const avgOperationalRisk =
    riskEntries.length > 0 ? riskEntries.reduce((s, [, v]) => s + Number(v), 0) / riskEntries.length : 0;

  const scores = rep.map((r) => r.score).filter((s) => s != null);
  const avgScore = scores.length ? scores.reduce((a, b) => a + b, 0) / scores.length : 0;
  const minScore = scores.length ? Math.min(...scores) : 0;
  const reputationDeterioration = Math.max(0, Math.round(70 - minScore));

  const frustrationIndex = Math.round(
    Math.min(100, negativeShare * 45 + avgComplaint * 0.35 + (alerts?.length || 0) * 4)
  );

  const premiumTopics = (data?.top_negative_topics || []).filter((t) =>
    /premium|business|first|lounge|crew/i.test(t.label || "")
  );
  const premiumDissatisfaction = premiumTopics.length
    ? Math.round(premiumTopics.reduce((s, t) => s + (t.weight || 0), 0) / premiumTopics.length)
    : Math.round(negativeShare * 30);

  const highAnomalies = (anomalies || []).filter((a) => a.severity === "high" || a.severity === "critical").length;

  return [
    {
      id: "operational_risk",
      labelKey: "metrics.operationalRisk",
      value: Math.round(avgOperationalRisk),
      unit: "",
      trend: avgOperationalRisk > 50 ? "down" : "up",
      severity: avgOperationalRisk > 60 ? "high" : avgOperationalRisk > 40 ? "medium" : "low"
    },
    {
      id: "frustration",
      labelKey: "metrics.frustration",
      value: frustrationIndex,
      unit: "",
      trend: frustrationIndex > 55 ? "down" : "stable",
      severity: frustrationIndex > 65 ? "high" : "medium"
    },
    {
      id: "premium_dissatisfaction",
      labelKey: "metrics.premiumDissatisfaction",
      value: premiumDissatisfaction,
      unit: "",
      trend: "down",
      severity: premiumDissatisfaction > 35 ? "high" : "medium"
    },
    {
      id: "complaint_density",
      labelKey: "metrics.complaintDensity",
      value: Math.round(avgComplaint),
      unit: "%",
      trend: avgComplaint > 40 ? "down" : "up",
      severity: avgComplaint > 50 ? "high" : "medium"
    },
    {
      id: "reputation_deterioration",
      labelKey: "metrics.reputationDeterioration",
      value: reputationDeterioration,
      unit: "pts",
      trend: reputationDeterioration > 15 ? "down" : "stable",
      severity: reputationDeterioration > 20 ? "critical" : reputationDeterioration > 10 ? "high" : "low"
    },
    {
      id: "active_signals",
      labelKey: "metrics.activeSignals",
      value: (alerts?.length || 0) + highAnomalies,
      unit: "",
      trend: "stable",
      severity: highAnomalies > 2 ? "critical" : highAnomalies > 0 ? "high" : "low"
    }
  ];
}

export function forecastConfidence(row) {
  if (!row) return { score: 0, insufficient: true, method: "—" };
  const payload = row.payload || {};
  const history = payload.history || [];
  const explicit = row.confidence_score ?? payload.confidence_score;
  if (row.insufficient_data || payload.insufficient_data) {
    return { score: 0, insufficient: true, method: row.forecast_method || row.method || "insufficient" };
  }
  if (explicit != null) {
    return {
      score: Math.round(Number(explicit) * (explicit <= 1 ? 100 : 1)),
      insufficient: false,
      method: row.forecast_method || row.method || "ewma"
    };
  }
  const n = history.length;
  const score = Math.min(95, Math.round(35 + n * 8));
  return {
    score,
    insufficient: n < 3,
    method: row.forecast_method || row.method || payload.method || "rolling_average"
  };
}
