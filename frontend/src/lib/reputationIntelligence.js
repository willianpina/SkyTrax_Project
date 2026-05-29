/**
 * Reputation Intelligence Layer
 * Transforms raw analytics data into operational intelligence for the reputation workspace.
 */

const RISK_THRESHOLDS = { critical: 30, high: 50, attention: 70, stable: 85 };

export function riskLevel(score) {
  if (score == null || score <= RISK_THRESHOLDS.critical) return "critical";
  if (score <= RISK_THRESHOLDS.high) return "high";
  if (score <= RISK_THRESHOLDS.attention) return "attention";
  if (score <= RISK_THRESHOLDS.stable) return "stable";
  return "excellent";
}

export function riskOrder(level) {
  const map = { critical: 5, high: 4, attention: 3, stable: 2, excellent: 1 };
  return map[level] || 0;
}

const REGION_MAP = {
  "United Kingdom": "europe", "Germany": "europe", "France": "europe", "Netherlands": "europe",
  "Switzerland": "europe", "Ireland": "europe", "Spain": "europe", "Italy": "europe",
  "Portugal": "europe", "Turkey": "europe", "Finland": "europe", "Norway": "europe",
  "Sweden": "europe", "Denmark": "europe", "Belgium": "europe", "Austria": "europe",
  "Poland": "europe", "Greece": "europe", "Iceland": "europe", "Luxembourg": "europe",
  "United States": "northAmerica", "Canada": "northAmerica",
  "Brazil": "latam", "Mexico": "latam", "Colombia": "latam", "Chile": "latam",
  "Argentina": "latam", "Peru": "latam", "Panama": "latam", "Costa Rica": "latam",
  "United Arab Emirates": "middleEast", "Qatar": "middleEast", "Saudi Arabia": "middleEast",
  "Oman": "middleEast", "Bahrain": "middleEast", "Jordan": "middleEast", "Kuwait": "middleEast",
  "China": "asia", "Japan": "asia", "South Korea": "asia", "Singapore": "asia",
  "Thailand": "asia", "Malaysia": "asia", "India": "asia", "Indonesia": "asia",
  "Vietnam": "asia", "Philippines": "asia", "Taiwan": "asia", "Hong Kong": "asia",
  "South Africa": "africa", "Kenya": "africa", "Ethiopia": "africa", "Egypt": "africa",
  "Morocco": "africa", "Nigeria": "africa",
  "Australia": "oceania", "New Zealand": "oceania", "Fiji": "oceania",
};

export function resolveRegion(country, backendRegion) {
  if (backendRegion) {
    const normalized = backendRegion.toLowerCase().replace(/\s+/g, "");
    if (normalized.includes("europe")) return "europe";
    if (normalized.includes("north")) return "northAmerica";
    if (normalized.includes("latin")) return "latam";
    if (normalized.includes("middle")) return "middleEast";
    if (normalized.includes("asia")) return "asia";
    if (normalized.includes("africa")) return "africa";
    if (normalized.includes("oceania")) return "oceania";
  }
  if (!country) return "other";
  return REGION_MAP[country] || "other";
}

export function buildReputationRegistry(reputation, benchmarking, anomalies, alerts, forecasts) {
  const rep = Array.isArray(reputation) ? reputation : [];
  const bm = benchmarking || {};
  const anomalyMap = new Map();
  for (const a of anomalies || []) {
    if (a.airline) anomalyMap.set(a.airline, (anomalyMap.get(a.airline) || 0) + 1);
  }
  for (const a of alerts || []) {
    if (a.airline) anomalyMap.set(a.airline, (anomalyMap.get(a.airline) || 0) + 1);
  }

  const forecastMap = new Map();
  if (forecasts?.metrics) {
    for (const [, airlines] of Object.entries(forecasts.metrics)) {
      for (const [slug, mData] of Object.entries(airlines || {})) {
        if (!forecastMap.has(slug)) forecastMap.set(slug, {});
        const existing = forecastMap.get(slug);
        existing.delta = (existing.delta || 0) + (mData.delta || 0);
        existing.trend = mData.trend || existing.trend;
      }
    }
  }

  const scored = rep
    .filter((r) => r.review_count > 0)
    .map((r) => {
      const score = Math.round((r.score || 0) * 10) / 10;
      const complaints = r.complaint_count ?? 0;
      const complaintsRatio = r.complaint_density ?? 0;
      const opRisk = bm.operational_risk?.[r.slug] ?? Math.round(complaintsRatio * 0.6 + (r.topic_negativity || 0) * 0.4);
      const incidents = anomalyMap.get(r.airline) || 0;
      const fc = forecastMap.get(r.slug) || {};
      const region = resolveRegion(r.country, r.region);
      const alliance = r.alliance || null;

      const historyScores = (r.history || []).map((h) => h.score);
      let trend;
      if (fc.trend) {
        trend = fc.trend;
      } else if (historyScores.length >= 2) {
        const recent = historyScores[historyScores.length - 1];
        const prev = historyScores[historyScores.length - 2];
        const diff = recent - prev;
        trend = diff > 2 ? "improving" : diff < -2 ? "declining" : "stable";
      } else {
        trend = "stable";
      }

      const stability = Math.max(0, Math.min(100,
        100 - Math.abs(fc.delta || 0) * 8 - incidents * 12 - complaintsRatio * 0.3
      ));

      return {
        slug: r.slug,
        airline: r.airline,
        country: r.country || "—",
        alliance,
        region,
        score,
        risk: riskLevel(score),
        trend,
        complaints,
        complaintsRatio: Math.round(complaintsRatio * 10) / 10,
        operationalRisk: Math.round(opRisk),
        stability: Math.round(stability),
        incidents,
        reviewCount: r.review_count || 0,
        negativeCount: r.negative_count || 0,
        starRating: r.star_rating || 0,
        airlineType: r.airline_type || null,
        iataCode: r.iata_code || null,
        icaoCode: r.icao_code || null,
        primaryHub: r.primary_hub || null,
        forecastDelta: Math.round((fc.delta || 0) * 10) / 10,
        historyScores,
      };
    })
    .sort((a, b) => riskOrder(b.risk) - riskOrder(a.risk) || a.score - b.score);

  scored.forEach((r, idx) => { r.rank = idx + 1; });
  return scored;
}

export function computeReputationKPIs(registry) {
  const total = registry.length;
  const critical = registry.filter((r) => r.risk === "critical" || r.risk === "high").length;
  const recovering = registry.filter((r) => r.forecastDelta > 2).length;
  const deteriorating = registry.filter((r) => r.forecastDelta < -2).length;
  const avgScore = total > 0 ? registry.reduce((s, r) => s + r.score, 0) / total : 0;
  const avgStability = total > 0 ? registry.reduce((s, r) => s + r.stability, 0) / total : 0;
  const totalIncidents = registry.reduce((s, r) => s + r.incidents, 0);
  const totalComplaints = registry.reduce((s, r) => s + r.complaints, 0);
  const totalReviews = registry.reduce((s, r) => s + r.reviewCount, 0);
  const emergingComplaints = registry.filter((r) => r.complaints > 20).length;

  const byAlliance = {};
  for (const r of registry) {
    const key = r.alliance || "independent";
    if (!byAlliance[key]) byAlliance[key] = { sum: 0, count: 0 };
    byAlliance[key].sum += r.score;
    byAlliance[key].count += 1;
  }
  const allianceAvgs = Object.fromEntries(
    Object.entries(byAlliance).map(([k, v]) => [k, Math.round(v.sum / v.count)])
  );

  const byRegion = {};
  for (const r of registry) {
    if (!byRegion[r.region]) byRegion[r.region] = { sum: 0, count: 0, risk: 0 };
    byRegion[r.region].sum += r.score;
    byRegion[r.region].count += 1;
    byRegion[r.region].risk += r.operationalRisk;
  }
  const regionalRisk = Object.entries(byRegion)
    .map(([k, v]) => ({ region: k, avgRisk: Math.round(v.risk / v.count), avgScore: Math.round(v.sum / v.count) }))
    .sort((a, b) => b.avgRisk - a.avgRisk);

  return {
    total,
    critical,
    recovering,
    deteriorating,
    avgScore: Math.round(avgScore * 10) / 10,
    avgStability: Math.round(avgStability),
    totalIncidents,
    totalComplaints,
    totalReviews,
    emergingComplaints,
    allianceAvgs,
    regionalRisk,
    worstRegion: regionalRisk[0] || null,
  };
}

export function extractPrioritySignals(registry) {
  const sorted = [...registry];
  const worstDeterioration = sorted.filter((r) => r.forecastDelta < -3).sort((a, b) => a.forecastDelta - b.forecastDelta).slice(0, 5);
  const bestRecovery = sorted.filter((r) => r.forecastDelta > 3).sort((a, b) => b.forecastDelta - a.forecastDelta).slice(0, 5);
  const criticalRisk = sorted.filter((r) => r.risk === "critical").slice(0, 5);
  const highComplaints = sorted.filter((r) => r.complaints > 10).sort((a, b) => b.complaints - a.complaints).slice(0, 5);
  const incidentCluster = sorted.filter((r) => r.incidents >= 2).sort((a, b) => b.incidents - a.incidents).slice(0, 5);

  return { worstDeterioration, bestRecovery, criticalRisk, highComplaints, incidentCluster };
}

export const GROUP_MODES = ["global", "region", "alliance", "risk", "trend"];

export function groupRegistry(registry, mode) {
  if (mode === "global") return [{ key: "all", label: "all", items: registry }];

  const map = new Map();
  for (const r of registry) {
    let key;
    switch (mode) {
      case "region": key = r.region; break;
      case "alliance": key = r.alliance || "independent"; break;
      case "risk": key = r.risk; break;
      case "trend": key = r.trend; break;
      default: key = "all";
    }
    if (!map.has(key)) map.set(key, []);
    map.get(key).push(r);
  }

  return Array.from(map.entries())
    .map(([key, items]) => ({ key, label: key, items }))
    .sort((a, b) => b.items.length - a.items.length);
}
