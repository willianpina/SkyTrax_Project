const SEV_RANK = { critical: 0, high: 1, medium: 2, low: 3 };

export function filterByAirline(items, selectedAirline, reputation = []) {
  if (!selectedAirline) return items || [];
  const rep = (reputation || []).find((r) => r.slug === selectedAirline);
  const carrierName = rep?.airline;
  return (items || []).filter(
    (item) =>
      item.airline_slug === selectedAirline ||
      item.slug === selectedAirline ||
      item.airline === selectedAirline ||
      (carrierName && item.airline === carrierName)
  );
}

export function investigationMetrics(anomalies, insights, selectedAirline, reputation = []) {
  const filtered = filterByAirline(anomalies, selectedAirline, reputation);
  const insightRows = filterByAirline(insights, selectedAirline, reputation);
  const carriers = new Set(filtered.map((a) => a.airline).filter(Boolean));
  const critical = filtered.filter(
    (a) => a.severity === "critical" || a.severity === "high"
  ).length;

  return {
    activeIncidents: filtered.length,
    carriersImpacted: carriers.size,
    criticalCases: critical,
    correlatedInsights: insightRows.length,
  };
}

export function sortIncidentsBySeverity(anomalies) {
  return [...(anomalies || [])].sort((a, b) => {
    const ra = SEV_RANK[a.severity] ?? 9;
    const rb = SEV_RANK[b.severity] ?? 9;
    if (ra !== rb) return ra - rb;
    return (b.detected_at || "").localeCompare(a.detected_at || "");
  });
}

export function humanizeType(type) {
  if (!type) return "";
  return type.replace(/_/g, " ");
}
