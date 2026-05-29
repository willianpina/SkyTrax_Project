export const RISK_MATRIX_KEYS = ["delays", "baggage", "crew"];

export const ALLIANCE_ORDER = ["Star Alliance", "SkyTeam", "Oneworld"];

export function riskTone(score) {
  if (score >= 60) return "high";
  if (score >= 35) return "medium";
  return "low";
}

export function scoreTone(score) {
  if (score >= 60) return "low";
  if (score >= 35) return "medium";
  return "high";
}

export function topHubRankings(rankings, limit = 10) {
  return [...(rankings || [])]
    .sort((a, b) => (b.operational_score ?? 0) - (a.operational_score ?? 0))
    .slice(0, limit);
}

export function resolveDominantCarrier(iata, concentration) {
  if (!iata) return "—";
  const code = String(iata).toUpperCase();
  const matches = (concentration || []).filter(
    (c) => String(c.primary_hub || "").toUpperCase() === code
  );
  if (!matches.length) return "—";
  const best = matches.sort(
    (a, b) => (b.concentration_ratio ?? 0) - (a.concentration_ratio ?? 0)
  )[0];
  return best?.airline_name || "—";
}

export function riskMatrixRows(hubRisk, limit = 12) {
  return [...(hubRisk || [])]
    .map((row) => {
      const risks = row.risks || {};
      const complaints = Object.values(risks).reduce((s, v) => s + (v || 0), 0);
      return {
        ...row,
        matrix: {
          delays: risks.delays || 0,
          baggage: risks.baggage || 0,
          crew: risks.crew || 0,
          complaints,
        },
        total: complaints,
      };
    })
    .sort((a, b) => b.total - a.total)
    .slice(0, limit);
}

export function sortAllianceHubs(alliances) {
  return [...(alliances || [])].sort((a, b) => {
    const ia = ALLIANCE_ORDER.indexOf(a.alliance_name);
    const ib = ALLIANCE_ORDER.indexOf(b.alliance_name);
    if (ia !== -1 && ib !== -1) return ia - ib;
    if (ia !== -1) return -1;
    if (ib !== -1) return 1;
    return (a.alliance_name || "").localeCompare(b.alliance_name || "");
  });
}

export function topConcentrationPairs(concentration, rankings, limit = 12) {
  const nameByIata = Object.fromEntries(
    (rankings || []).map((r) => [String(r.iata || "").toUpperCase(), r.airport_name])
  );
  return [...(concentration || [])]
    .sort((a, b) => (b.concentration_ratio ?? 0) - (a.concentration_ratio ?? 0))
    .slice(0, limit)
    .map((row) => {
      const iata = String(row.primary_hub || "").toUpperCase();
      const hubLabel = nameByIata[iata] || iata || "—";
      return {
        id: row.airline_slug || row.airline_name,
        hub: hubLabel,
        iata,
        airline: row.airline_name,
        ratio: row.concentration_ratio ?? 0,
        exposure: row.exposure_risk || "low",
      };
    });
}

export function buildHubInsights(rankings, concentration, dashboard, t) {
  const items = [];
  const sorted = topHubRankings(rankings, rankings?.length || 0);
  if (!sorted.length) return items;

  const resilient = [...sorted].sort(
    (a, b) => (b.operational_score ?? 0) - (a.operational_score ?? 0) || (a.risk_score ?? 0) - (b.risk_score ?? 0)
  )[0];
  if (resilient) {
    items.push({
      id: "resilient",
      hub: resilient.airport_name,
      title: t("insightResilient"),
      detail: t("insightResilientDetail", {
        score: (resilient.operational_score ?? 0).toFixed(1),
        risk: (resilient.risk_score ?? 0).toFixed(1),
      }),
      metric: t("insightScore", { value: (resilient.operational_score ?? 0).toFixed(1) }),
      severity: "low",
    });
  }

  const critical = [...sorted].sort((a, b) => (b.risk_score ?? 0) - (a.risk_score ?? 0))[0];
  if (critical && critical.iata !== resilient?.iata) {
    items.push({
      id: "critical",
      hub: critical.airport_name,
      title: t("insightCritical"),
      detail: t("insightCriticalDetail", { risk: (critical.risk_score ?? 0).toFixed(1) }),
      metric: t("insightRisk", { value: (critical.risk_score ?? 0).toFixed(1) }),
      severity: "high",
    });
  }

  const growth = [...sorted].sort((a, b) => (b.mention_count ?? 0) - (a.mention_count ?? 0))[0];
  if (growth) {
    items.push({
      id: "growth",
      hub: growth.airport_name,
      title: t("insightGrowth"),
      detail: t("insightGrowthDetail", { mentions: growth.mention_count ?? 0 }),
      metric: `+${growth.mention_count ?? 0}`,
      severity: "medium",
    });
  }

  const pairs = topConcentrationPairs(concentration, rankings, 1);
  if (pairs[0]) {
    const p = pairs[0];
    items.push({
      id: "concentrated",
      hub: p.hub,
      title: t("insightConcentrated"),
      detail: t("insightConcentratedDetail", { airline: p.airline }),
      metric: `${Math.round(p.ratio * 100)}%`,
      severity: p.exposure === "critical" ? "high" : "medium",
    });
  }

  if (dashboard?.critical_hubs > 0) {
    items.push({
      id: "ops",
      hub: t("insightOpsHub"),
      title: t("insightOpsTitle"),
      detail: t("insightOpsDetail", { count: dashboard.critical_hubs }),
      metric: String(dashboard.critical_hubs),
      severity: "high",
    });
  }

  return items.slice(0, 6);
}
