const TYPE_VARIANTS = {
  full_service: "info",
  low_cost: "warning",
  regional: "neutral",
  cargo: "neutral",
  charter: "neutral",
  hybrid: "info",
};

export const ALLIANCE_COLORS = {
  "Star Alliance": "var(--ops-cyan, #22d3ee)",
  Oneworld: "var(--ops-red, #ef4444)",
  SkyTeam: "var(--ops-blue, #3b82f6)",
};

export function formatAirlineType(raw, t) {
  if (!raw) return null;
  const key = raw.toLowerCase().replace(/\s+/g, "_");
  const variant = TYPE_VARIANTS[key] || "neutral";
  const label = t(`types.${key}`, { defaultValue: raw.replace(/_/g, " ") });
  return { label, variant };
}

export function resolveMetric(value, fallback = 0) {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof fallback === "number" && Number.isFinite(fallback)) return fallback;
  return 0;
}
