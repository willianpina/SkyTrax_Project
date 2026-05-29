export const ALLIANCE_THEME = {
  "Star Alliance": { accent: "#eab308", label: "Star Alliance" },
  Oneworld: { accent: "#ef4444", label: "Oneworld" },
  SkyTeam: { accent: "#3b82f6", label: "SkyTeam" },
};

const ORDER = ["Star Alliance", "SkyTeam", "Oneworld"];

export function sortAlliances(alliances) {
  return [...(alliances || [])].sort((a, b) => {
    const ia = ORDER.indexOf(a.name);
    const ib = ORDER.indexOf(b.name);
    if (ia !== -1 && ib !== -1) return ia - ib;
    if (ia !== -1) return -1;
    if (ib !== -1) return 1;
    return (a.name || "").localeCompare(b.name || "");
  });
}

export function allianceOverviewMetrics(alliances) {
  const list = alliances || [];
  const totalMembers = list.reduce((s, a) => s + (a.member_count || 0), 0);
  const totalReviews = list.reduce((s, a) => s + (a.total_reviews || 0), 0);
  const avgRisk =
    list.length > 0
      ? Math.round(list.reduce((s, a) => s + (a.operational_risk || 0), 0) / list.length)
      : 0;
  const best = list.reduce(
    (top, a) => ((a.avg_rating || 0) > (top?.avg_rating || 0) ? a : top),
    list[0] || null
  );
  return {
    allianceCount: list.length,
    totalMembers,
    totalReviews,
    avgRisk,
    bestAlliance: best?.name || "—",
    bestRating: best?.avg_rating || 0,
  };
}

export function riskLevel(risk) {
  if (risk > 50) return "high";
  if (risk > 30) return "medium";
  return "low";
}

export function buildAnalyticsFeedItems(alliances, fusionSignals, t) {
  const sorted = sortAlliances(alliances);
  const fromSignals = (fusionSignals || [])
    .filter(
      (s) =>
        s.category === "alliance_deterioration" ||
        (s.entities || []).some((e) =>
          sorted.some((a) => a.name?.toLowerCase() === String(e).toLowerCase())
        )
    )
    .slice(0, 4)
    .map((s) => ({
      id: s.id,
      alliance: (s.entities || [])[0] || s.title,
      title: s.title,
      detail: s.description,
      metric: `${Math.round((s.confidence || 0) * 100)}%`,
      severity: s.severity || "medium",
    }));

  if (fromSignals.length > 0) return fromSignals;

  return sorted.slice(0, 6).map((a) => {
    const risk = a.operational_risk || 0;
    const sev = risk > 50 ? "high" : risk > 30 ? "medium" : "low";
    return {
      id: a.id,
      alliance: a.name,
      title:
        sev === "low"
          ? t("feedLeadingReputation")
          : sev === "high"
            ? t("feedElevatedRisk")
            : t("feedWatchlist"),
      detail: t("feedMembersReviews", {
        members: a.member_count || 0,
        reviews: (a.total_reviews || 0).toLocaleString(),
      }),
      metric: t("feedScore", { value: (a.avg_rating || 0).toFixed(1) }),
      severity: sev,
    };
  });
}

export function heatmapCells(alliance) {
  const risk = alliance.operational_risk || 0;
  return {
    reputation: Math.max(0, 100 - risk),
    sentiment: Math.max(0, Math.min(100, 100 - risk * 0.7)),
    complaints: Math.min(100, risk * 0.85),
    risk: risk,
    stability: Math.max(0, 100 - risk * 0.6),
  };
}
