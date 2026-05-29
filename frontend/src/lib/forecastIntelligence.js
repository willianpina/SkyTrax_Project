/** Forecast intelligence — noise suppression, top movers, and executive synthesis */

const THRESHOLDS = {
  reputation_score: 2.0,
  sentiment: 3.0,
  complaint_density: 5.0
};

export function computeDelta(current, forecast) {
  if (current == null || forecast == null) return 0;
  return +(forecast - current).toFixed(2);
}

export function isSignificant(metric, delta) {
  const threshold = THRESHOLDS[metric] ?? 2.0;
  return Math.abs(delta) >= threshold;
}

export function riskLevel(delta, metric) {
  const abs = Math.abs(delta);
  const t = THRESHOLDS[metric] ?? 2.0;
  if (metric === "complaint_density" || metric === "sentiment") {
    if (delta > t * 3) return "critical";
    if (delta > t * 2) return "high";
    if (delta > t) return "medium";
    return "low";
  }
  if (delta < -t * 3) return "critical";
  if (delta < -t * 2) return "high";
  if (abs > t) return "medium";
  return "low";
}

export function buildAirlineForecasts(forecasts, reputation) {
  const metrics = forecasts?.metrics || {};
  const airlineMap = new Map();

  for (const [metric, rows] of Object.entries(metrics)) {
    const weeklyRows = (Array.isArray(rows) ? rows : []).filter((r) => r.horizon === "weekly");
    for (const row of weeklyRows) {
      const slug = row.airline_slug;
      if (!slug) continue;
      if (!airlineMap.has(slug)) {
        airlineMap.set(slug, { slug, airline: row.airline, metrics: {} });
      }
      const delta = computeDelta(row.current_value, row.forecast_value);
      airlineMap.get(slug).metrics[metric] = {
        current: row.current_value,
        forecast: row.forecast_value,
        delta,
        trend: row.trend_direction,
        method: row.method || row.forecast_method,
        significant: isSignificant(metric, delta),
        risk: riskLevel(delta, metric),
        payload: row.payload
      };
    }
  }

  const repMap = new Map();
  if (Array.isArray(reputation)) {
    for (const r of reputation) {
      repMap.set(r.slug, r);
    }
  }

  const result = [];
  for (const [slug, entry] of airlineMap) {
    const rep = repMap.get(slug);
    const repMetric = entry.metrics.reputation_score || {};
    const sentMetric = entry.metrics.sentiment || {};
    const compMetric = entry.metrics.complaint_density || {};

    const scoreCurrent = repMetric.current ?? rep?.score ?? 0;
    const scoreForecast = repMetric.forecast ?? scoreCurrent;
    const scoreDelta = computeDelta(scoreCurrent, scoreForecast);

    const overallRisk = worstRisk([repMetric.risk, sentMetric.risk, compMetric.risk]);

    const confidence = computeAirlineConfidence(entry.metrics);

    result.push({
      slug,
      airline: entry.airline || rep?.airline || slug,
      scoreCurrent: Math.round(scoreCurrent * 10) / 10,
      scoreForecast: Math.round(scoreForecast * 10) / 10,
      scoreDelta: Math.round(scoreDelta * 10) / 10,
      trend: repMetric.trend || "stable",
      risk: overallRisk,
      confidence,
      complaints: Math.round((compMetric.current ?? rep?.complaint_density ?? 0) * 10) / 10,
      complaintDelta: Math.round((compMetric.delta ?? 0) * 10) / 10,
      sentiment: Math.round((sentMetric.current ?? 0) * 10) / 10,
      sentimentDelta: Math.round((sentMetric.delta ?? 0) * 10) / 10,
      metrics: entry.metrics,
      alliance: rep?.alliance || null,
      region: rep?.region || null,
      type: rep?.type || null
    });
  }

  return result.sort((a, b) => riskOrder(b.risk) - riskOrder(a.risk) || a.scoreDelta - b.scoreDelta);
}

function worstRisk(risks) {
  const order = { critical: 4, high: 3, medium: 2, low: 1 };
  let worst = "low";
  for (const r of risks) {
    if (r && (order[r] || 0) > (order[worst] || 0)) worst = r;
  }
  return worst;
}

function riskOrder(risk) {
  return { critical: 4, high: 3, medium: 2, low: 1 }[risk] || 0;
}

function computeAirlineConfidence(metrics) {
  const scores = [];
  for (const m of Object.values(metrics)) {
    const payload = m.payload || {};
    const explicit = payload.confidence_score;
    if (explicit != null) {
      scores.push(Number(explicit) * (explicit <= 1 ? 100 : 1));
    } else {
      const history = payload.history || [];
      scores.push(Math.min(95, 35 + history.length * 8));
    }
  }
  return scores.length ? Math.round(scores.reduce((a, b) => a + b, 0) / scores.length) : 0;
}

export function extractTopMovers(airlines, limit = 5) {
  if (!airlines.length) return [];

  const significant = airlines.filter(
    (a) => a.risk !== "low" || Math.abs(a.scoreDelta) >= THRESHOLDS.reputation_score
  );

  const sorted = [...significant].sort((a, b) => Math.abs(b.scoreDelta) - Math.abs(a.scoreDelta));
  return sorted.slice(0, limit);
}

export function computeExecutiveSummary(airlines) {
  const total = airlines.length;
  const deteriorating = airlines.filter((a) => a.scoreDelta < -THRESHOLDS.reputation_score).length;
  const recovering = airlines.filter((a) => a.scoreDelta > THRESHOLDS.reputation_score).length;
  const risks = airlines.map((a) => riskOrder(a.risk));
  const avgRisk = risks.length ? risks.reduce((s, r) => s + r, 0) / risks.length : 0;
  const avgConfidence = airlines.length
    ? Math.round(airlines.reduce((s, a) => s + a.confidence, 0) / airlines.length)
    : 0;

  const criticalAlerts = airlines.filter((a) => a.risk === "critical" || a.risk === "high");
  const topAlert = criticalAlerts.length > 0 ? criticalAlerts[0] : null;

  return {
    total,
    deteriorating,
    recovering,
    avgRisk: riskLabel(avgRisk),
    avgRiskValue: avgRisk,
    topAlert,
    avgConfidence,
    stable: total - deteriorating - recovering
  };
}

function riskLabel(value) {
  if (value >= 3.5) return "critical";
  if (value >= 2.5) return "high";
  if (value >= 1.5) return "medium";
  return "low";
}

export function buildTemporalHeatmap(airlines) {
  return airlines.map((a) => {
    const payload = a.metrics?.reputation_score?.payload || {};
    const history = payload.history || [];
    const forecastPts = payload.forecast_points || [];

    const recent7 = sliceDelta(history, 7);
    const recent30 = sliceDelta(history, 30);
    const recent90 = sliceDelta(history, 90);
    const projected = forecastPts.length ? forecastPts[forecastPts.length - 1].value - (a.scoreCurrent || 0) : 0;

    return {
      slug: a.slug,
      airline: a.airline,
      d7: +recent7.toFixed(1),
      d30: +recent30.toFixed(1),
      d90: +recent90.toFixed(1),
      projected: +projected.toFixed(1)
    };
  });
}

function sliceDelta(history, days) {
  if (history.length < 2) return 0;
  const cutoff = history.length - Math.min(days, history.length);
  const start = history[cutoff]?.value ?? history[0]?.value ?? 0;
  const end = history[history.length - 1]?.value ?? 0;
  return end - start;
}
