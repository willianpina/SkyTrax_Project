const HEALTH_STATES = {
  OPERATIONAL: "operational",
  PARTIAL: "partial",
  DEGRADED: "degraded",
  SAFE_MODE: "safe_mode",
  MAINTENANCE: "maintenance",
  SYNCING: "syncing",
  STANDBY: "standby",
  CRITICAL: "critical",
  OFFLINE: "offline",
};

const STATE_PRIORITY = {
  [HEALTH_STATES.OPERATIONAL]: 0,
  [HEALTH_STATES.SYNCING]: 1,
  [HEALTH_STATES.STANDBY]: 2,
  [HEALTH_STATES.MAINTENANCE]: 3,
  [HEALTH_STATES.PARTIAL]: 4,
  [HEALTH_STATES.DEGRADED]: 5,
  [HEALTH_STATES.SAFE_MODE]: 6,
  [HEALTH_STATES.CRITICAL]: 7,
  [HEALTH_STATES.OFFLINE]: 8,
};

const SCORE_IMPACT = {
  [HEALTH_STATES.OPERATIONAL]: 0,
  [HEALTH_STATES.SYNCING]: 3,
  [HEALTH_STATES.STANDBY]: 8,
  [HEALTH_STATES.MAINTENANCE]: 12,
  [HEALTH_STATES.PARTIAL]: 16,
  [HEALTH_STATES.DEGRADED]: 28,
  [HEALTH_STATES.SAFE_MODE]: 22,
  [HEALTH_STATES.CRITICAL]: 45,
  [HEALTH_STATES.OFFLINE]: 70,
};

const BADGE_LABEL = {
  [HEALTH_STATES.OPERATIONAL]: "Operational",
  [HEALTH_STATES.PARTIAL]: "Partial",
  [HEALTH_STATES.DEGRADED]: "Degraded",
  [HEALTH_STATES.SAFE_MODE]: "Safe Mode",
  [HEALTH_STATES.MAINTENANCE]: "Maintenance",
  [HEALTH_STATES.SYNCING]: "Syncing",
  [HEALTH_STATES.STANDBY]: "Standby",
  [HEALTH_STATES.CRITICAL]: "Critical",
  [HEALTH_STATES.OFFLINE]: "Offline",
};

const BADGE_SEVERITY = {
  [HEALTH_STATES.OPERATIONAL]: "ok",
  [HEALTH_STATES.PARTIAL]: "warn",
  [HEALTH_STATES.DEGRADED]: "warn",
  [HEALTH_STATES.SAFE_MODE]: "info",
  [HEALTH_STATES.MAINTENANCE]: "info",
  [HEALTH_STATES.SYNCING]: "info",
  [HEALTH_STATES.STANDBY]: "neutral",
  [HEALTH_STATES.CRITICAL]: "error",
  [HEALTH_STATES.OFFLINE]: "error",
};

function normalizeReadiness(raw) {
  const value = String(raw || "").toLowerCase();
  if (["healthy", "ok", "operational"].includes(value)) return HEALTH_STATES.OPERATIONAL;
  if (["degraded", "partial"].includes(value)) return HEALTH_STATES.DEGRADED;
  if (["critical", "failed"].includes(value)) return HEALTH_STATES.CRITICAL;
  if (["offline", "down"].includes(value)) return HEALTH_STATES.OFFLINE;
  return HEALTH_STATES.STANDBY;
}

function worstState(states) {
  return states.reduce((worst, current) => (
    STATE_PRIORITY[current] > STATE_PRIORITY[worst] ? current : worst
  ), HEALTH_STATES.OPERATIONAL);
}

function categoryFromSignals(base, flags = {}) {
  if (flags.offline) return HEALTH_STATES.OFFLINE;
  if (flags.critical) return HEALTH_STATES.CRITICAL;
  if (flags.safeMode) return HEALTH_STATES.SAFE_MODE;
  if (flags.degraded) return HEALTH_STATES.DEGRADED;
  if (flags.partial) return HEALTH_STATES.PARTIAL;
  if (flags.syncing) return HEALTH_STATES.SYNCING;
  if (flags.maintenance) return HEALTH_STATES.MAINTENANCE;
  return base;
}

function toTitle(state) {
  return BADGE_LABEL[state] || "Operational";
}

export function deriveOperationalHealth(health = {}) {
  const readinessState = normalizeReadiness(health.readiness);
  const endpointsUnavailable = !!health.endpointsUnavailable;
  const pipelineDegraded = !!health.pipeline?.degraded;
  const safeMode = !!(health.runtime?.forecast_safe_mode_active || health.native?.safe_mode_active);
  const schemaDrift = !!(health.schema?.migration_drift || health.runtime?.schema_drift);
  const subprocessCooldown = !!health.runtime?.subprocess_cooldown_active;
  const blockedStages = Array.isArray(health.blocked_stages) ? health.blocked_stages : [];
  const degradedHistory = Array.isArray(health.degraded_history) ? health.degraded_history : [];
  const syncing = !!(health.orchestration?.active || health.pipeline?.running || health.runtime?.syncing_active);
  const maintenance = !!health.runtime?.maintenance_mode_active;
  const critical = !!(health.alembic?.safe === false && health.alembic?.chain_valid === false);

  const categories = {
    ingestion: categoryFromSignals(readinessState, { offline: endpointsUnavailable, critical }),
    enrichment: categoryFromSignals(readinessState, { safeMode, degraded: pipelineDegraded }),
    geospatial: categoryFromSignals(readinessState, { degraded: pipelineDegraded && blockedStages.some((s) => String(s).toLowerCase().includes("geo")) }),
    ai: categoryFromSignals(readinessState, { safeMode, degraded: pipelineDegraded }),
    correlation: categoryFromSignals(readinessState, { degraded: pipelineDegraded || blockedStages.some((s) => String(s).toLowerCase().includes("correlation") || String(s).toLowerCase().includes("fusion")) }),
    analytics: categoryFromSignals(readinessState, { degraded: pipelineDegraded, partial: degradedHistory.length > 0 }),
    synchronization: categoryFromSignals(readinessState, { syncing, degraded: subprocessCooldown }),
    recommendation_engine: categoryFromSignals(readinessState, { safeMode, degraded: pipelineDegraded }),
    operational_alerts: categoryFromSignals(readinessState, { partial: degradedHistory.length > 0 || blockedStages.length > 0 }),
  };

  const globalStatus = worstState([
    ...Object.values(categories),
    endpointsUnavailable ? HEALTH_STATES.OFFLINE : HEALTH_STATES.OPERATIONAL,
    critical ? HEALTH_STATES.CRITICAL : HEALTH_STATES.OPERATIONAL,
    safeMode ? HEALTH_STATES.SAFE_MODE : HEALTH_STATES.OPERATIONAL,
    pipelineDegraded ? HEALTH_STATES.DEGRADED : HEALTH_STATES.OPERATIONAL,
    schemaDrift ? HEALTH_STATES.PARTIAL : HEALTH_STATES.OPERATIONAL,
    maintenance ? HEALTH_STATES.MAINTENANCE : HEALTH_STATES.OPERATIONAL,
  ]);

  const penalty = Object.values(categories).reduce((sum, state) => sum + SCORE_IMPACT[state], 0);
  const operationalHealthScore = Math.max(0, Math.min(100, Math.round(100 - (penalty / Object.keys(categories).length))));

  const affectedServices = [];
  if (blockedStages.some((s) => String(s).toLowerCase().includes("correlation") || String(s).toLowerCase().includes("fusion"))) {
    affectedServices.push("Alliance correlation");
  }
  if (safeMode) affectedServices.push("Premium classification pipeline");
  if (schemaDrift) affectedServices.push("Runtime schema validation");
  if (subprocessCooldown) affectedServices.push("Subprocess enrichment workers");

  const title = globalStatus === HEALTH_STATES.DEGRADED
    ? "Operational degradation detected"
    : globalStatus === HEALTH_STATES.SAFE_MODE
      ? "Runtime protection mode enabled"
      : globalStatus === HEALTH_STATES.CRITICAL
        ? "Critical operational state detected"
        : globalStatus === HEALTH_STATES.OFFLINE
          ? "Operational runtime offline"
          : `Runtime ${toTitle(globalStatus)}`;

  const cause = safeMode
    ? "Advanced enrichment temporarily reduced to preserve operational stability."
    : pipelineDegraded
      ? "Partial degradation detected in operational pipelines."
      : endpointsUnavailable
        ? "Health API endpoint currently unavailable."
        : "Core operational pipelines are responding within runtime thresholds.";

  const impact = globalStatus === HEALTH_STATES.OPERATIONAL
    ? "No active operational impact detected."
    : globalStatus === HEALTH_STATES.SAFE_MODE
      ? "Recommendation confidence may be temporarily reduced while core services remain protected."
      : globalStatus === HEALTH_STATES.DEGRADED
        ? "Reduced recommendation accuracy and delayed enrichment signals may occur."
        : globalStatus === HEALTH_STATES.CRITICAL
          ? "Critical runtime capabilities are impaired; immediate intervention recommended."
          : globalStatus === HEALTH_STATES.OFFLINE
            ? "Operational intelligence endpoints are offline."
            : "Partial operational impact detected.";

  const currentState = globalStatus === HEALTH_STATES.OFFLINE
    ? "Core systems currently unavailable."
    : "Core operational systems remain active.";

  const tooltip = [
    title,
    `Cause: ${cause}`,
    `Impact: ${impact}`,
    `Current state: ${currentState}`,
    affectedServices.length ? `Affected services: ${affectedServices.join(" | ")}` : null,
    `Health score: ${operationalHealthScore}/100`,
  ].filter(Boolean).join("\n");

  return {
    globalStatus,
    operationalHealthScore,
    categories,
    affectedServices,
    summary: { title, cause, impact, currentState },
    badge: {
      key: "runtime_health",
      label: BADGE_LABEL[globalStatus] || "Operational",
      severity: BADGE_SEVERITY[globalStatus] || "neutral",
      variant: globalStatus,
      tooltip,
    },
  };
}

