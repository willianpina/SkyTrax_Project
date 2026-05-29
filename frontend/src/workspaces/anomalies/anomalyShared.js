import { useMemo } from "react";

export const SEV_ORDER = ["critical", "high", "medium", "low"];

export const SEV_CONFIG = {
  critical: { variant: "danger", labelKey: "critical" },
  high: { variant: "danger", labelKey: "high" },
  medium: { variant: "warning", labelKey: "medium" },
  low: { variant: "info", labelKey: "low" },
};

export function categorizeAnomaly(type) {
  const s = (type || "").toLowerCase();
  if (s.includes("reputation") || s.includes("score")) return "reputation";
  if (s.includes("sentiment") || s.includes("rating")) return "sentiment";
  if (s.includes("complaint") || s.includes("density")) return "complaints";
  if (s.includes("service") || s.includes("crew") || s.includes("cabin")) return "service";
  if (s.includes("delay") || s.includes("cancel")) return "operations";
  return "signal";
}

export function useSeverityCounts(anomalies, alerts) {
  return useMemo(() => {
    const c = { critical: 0, high: 0, medium: 0, low: 0 };
    for (const a of anomalies || []) c[a.severity] = (c[a.severity] || 0) + 1;
    for (const a of alerts || []) c[a.severity] = (c[a.severity] || 0) + 1;
    return c;
  }, [anomalies, alerts]);
}

export function useCarriersAffected(anomalies, alerts) {
  return useMemo(() => {
    const set = new Set();
    for (const a of anomalies || []) if (a.airline) set.add(a.airline);
    for (const a of alerts || []) if (a.airline) set.add(a.airline);
    return set.size;
  }, [anomalies, alerts]);
}

export function useGroupedAnomalies(anomalies) {
  return useMemo(() => {
    const byAirline = {};
    for (const a of anomalies || []) {
      const key = a.airline || "Unknown";
      if (!byAirline[key]) byAirline[key] = { airline: key, items: [], severities: {} };
      byAirline[key].items.push(a);
      const sev = a.severity || "low";
      byAirline[key].severities[sev] = (byAirline[key].severities[sev] || 0) + 1;
    }

    const groups = Object.values(byAirline);
    groups.sort((a, b) => {
      const score = (g) =>
        (g.severities.critical || 0) * 100 +
        (g.severities.high || 0) * 10 +
        (g.severities.medium || 0);
      return score(b) - score(a);
    });
    return groups;
  }, [anomalies]);
}

export function flattenGroups(groups) {
  const flat = [];
  for (const g of groups) {
    for (const item of g.items) {
      flat.push({ ...item, groupAirline: g.airline });
    }
  }
  return flat;
}
