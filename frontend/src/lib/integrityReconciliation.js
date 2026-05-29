/** Pipeline Integrity — defensive, runtime-authoritative KPI reconciliation. */

const DEV = typeof import.meta !== "undefined" && import.meta.env?.DEV;

/** @type {{ safeFallbacks: number, nullSafeHits: number, partialPayloads: number, recoveries: number }} */
const _metrics = {
  safeFallbacks: 0,
  nullSafeHits: 0,
  partialPayloads: 0,
  recoveries: 0,
};

function logRecon(tag, detail) {
  if (DEV) console.debug(`[${tag}]`, detail);
}

export function getReconciliationMetrics() {
  return { ..._metrics };
}

export function resetReconciliationMetrics() {
  _metrics.safeFallbacks = 0;
  _metrics.nullSafeHits = 0;
  _metrics.partialPayloads = 0;
  _metrics.recoveries = 0;
}

function bump(key) {
  _metrics[key] = (_metrics[key] || 0) + 1;
}

/** Plain object guard — does NOT coerce null/undefined into {}. */
export function isRecord(v) {
  return v != null && typeof v === "object" && !Array.isArray(v);
}

export function safeObj(v) {
  return isRecord(v) ? v : {};
}

export function safeNum(v, fallback = 0) {
  if (typeof v === "number" && Number.isFinite(v) && v >= 0) return v;
  if (typeof v === "string" && v.trim() !== "" && !Number.isNaN(Number(v))) {
    const n = Number(v);
    if (Number.isFinite(n) && n >= 0) return n;
  }
  if (v != null && v !== 0) bump("nullSafeHits");
  return fallback;
}

function maxPos(...vals) {
  let best = 0;
  let source = "empty";
  for (const [v, src] of vals) {
    const n = safeNum(v);
    if (n > best) {
      best = n;
      source = src;
    }
  }
  return { value: best, source };
}

/** Read nested path without throwing (e.g. fusion.signals_generated). */
export function getNestedValue(root, path) {
  if (!path || !isRecord(root)) return undefined;
  const parts = String(path).split(".");
  let cur = root;
  for (const part of parts) {
    if (!isRecord(cur)) return undefined;
    cur = cur[part];
  }
  return cur;
}

export function safeStage(stageResults, stageKey) {
  return safeObj(isRecord(stageResults) ? stageResults[stageKey] : undefined);
}

export function safeMetric(stageBlob, key, fallback = 0) {
  if (!key) return fallback;
  let raw;
  if (isRecord(stageBlob) && Object.prototype.hasOwnProperty.call(stageBlob, key)) {
    raw = stageBlob[key];
  } else if (key.includes(".")) {
    raw = getNestedValue(stageBlob, key);
  } else {
    raw = stageBlob?.[key];
  }
  const n = safeNum(raw, fallback);
  if (n > 0) return n;
  if (raw == null) bump("safeFallbacks");
  return fallback;
}

export function safeIntegrity(integrity) {
  const base = safeObj(integrity);
  return {
    ...base,
    table_counts: safeObj(base.table_counts),
    coverage: safeObj(base.coverage),
    kpi_lineage: safeObj(base.kpi_lineage),
    stage_results: safeObj(base.stage_results),
    metrics: safeObj(base.metrics),
    kpis: safeObj(base.kpis),
    canonical_kpis: safeObj(base.canonical_kpis),
    accumulated_kpis: safeObj(base.accumulated_kpis),
    authoritative_kpis: safeObj(base.authoritative_kpis),
  };
}

export function safeLineage(lineage) {
  return safeObj(lineage);
}

/**
 * Normalize integrity + pipeline inputs so downstream never sees undefined roots.
 */
export function normalizeIntegrityPayload(integrity, kpis, stageResults) {
  const base = safeIntegrity(integrity);
  const normalized = {
    ...base,
    table_counts: { ...base.table_counts },
    coverage: { ...base.coverage },
    kpi_lineage: { ...base.kpi_lineage },
    metrics: { ...base.metrics },
    kpis: { ...safeObj(kpis) },
    stage_results: { ...safeObj(stageResults) },
    canonical_kpis: { ...base.canonical_kpis },
    accumulated_kpis: { ...base.accumulated_kpis },
    authoritative_kpis: { ...base.authoritative_kpis },
  };

  const partial =
    !isRecord(integrity) ||
    !isRecord(integrity.table_counts) ||
    !isRecord(kpis) ||
    !isRecord(stageResults);

  if (partial) {
    bump("partialPayloads");
    logRecon("PARTIAL_PAYLOAD", { integrity: !!integrity, kpis: !!kpis, stageResults: !!stageResults });
  }

  logRecon("INTEGRITY_NORMALIZATION", {
    countsKeys: Object.keys(normalized.table_counts).length,
    stageKeys: Object.keys(normalized.stage_results).length,
  });

  return { ...normalized, partial };
}

export function stageMetric(stageResults, stageKey, ...keys) {
  const blob = safeStage(stageResults, stageKey);
  for (const key of keys) {
    const val = safeMetric(blob, key, -1);
    if (val > 0) {
      logRecon("SAFE_METRIC", { stage: stageKey, key, val });
      return val;
    }
  }
  return 0;
}

const EMPTY_LIVE_KPIS = Object.freeze({
  reviews: 0,
  metadata: 0,
  graph_nodes: 0,
  graph_edges: 0,
  signals: 0,
  anomalies: 0,
  clusters: 0,
  snapshots: 0,
});

/** Build live KPI map from Redis status.kpis + stage_results fallbacks. */
export function extractLiveKpis(kpis, stageResults) {
  try {
    const k = safeObj(kpis);
    const sr = safeObj(stageResults);
    const kg = safeStage(sr, "knowledge_graph");
    const fusion = safeStage(sr, "fusion");
    return {
      reviews: maxPos([k.reviews, "kpis"], [stageMetric(sr, "crawl", "total_reviews_in_db", "reviews_total"), "stage"]).value,
      metadata: maxPos([k.metadata, "kpis"], [stageMetric(sr, "metadata", "metadata_total", "reviews_analyzed"), "stage"]).value,
      graph_nodes: maxPos(
        [k.graph_nodes, "kpis"],
        [kg.total_nodes, "knowledge_graph"],
        [fusion?.upstream_validation?.graph_nodes_loaded, "fusion_upstream"],
      ).value,
      graph_edges: maxPos(
        [k.graph_edges, "kpis"],
        [kg.total_edges, "knowledge_graph"],
        [fusion?.upstream_validation?.graph_edges_loaded, "fusion_upstream"],
      ).value,
      signals: maxPos(
        [k.signals, "kpis"],
        [stageMetric(sr, "fusion", "fusion.signals_generated", "signals_generated"), "stage"],
        [fusion.signals_generated, "fusion_root"],
        [safeMetric(fusion, "metrics.signals_generated"), "fusion_metrics"],
      ).value,
      anomalies: maxPos([k.anomalies, "kpis"], [stageMetric(sr, "anomalies", "anomalies_created"), "stage"]).value,
      clusters: maxPos([k.clusters, "kpis"], [stageMetric(sr, "semantic", "clusters_created"), "stage"]).value,
      snapshots: maxPos(
        [k.snapshots, "kpis"],
        [stageMetric(sr, "snapshots", "snapshots_created", "metric_snapshots"), "stage"],
      ).value,
    };
  } catch (err) {
    bump("recoveries");
    logRecon("RECONCILIATION_SAFE", { fn: "extractLiveKpis", error: String(err?.message || err) });
    return { ...EMPTY_LIVE_KPIS };
  }
}

/** KPI live key → integrity table_counts key */
const COUNT_KEYS = {
  reviews: "reviews",
  metadata: "review_intelligence",
  graph_nodes: "graph_nodes",
  graph_edges: "graph_edges",
  signals: "fusion_signals",
  anomalies: "anomaly_events",
  snapshots: "metric_snapshots",
};

const EMPTY_DISPLAY = Object.freeze({
  table_counts: {},
  coverage: {},
  integrity_reconciled: false,
  runtime_authoritative: false,
  integrity_consistent: true,
  kpi_lineage: {},
  hasData: false,
  unavailable: true,
  partial: true,
  safe_fallback: true,
  core_operational_healthy: false,
  enrichment_warning: false,
  display: {
    metadataCoveragePct: undefined,
    graphNodes: 0,
    graphEdges: 0,
    graphEntities: 0,
    signals: 0,
    anomalies: 0,
    snapshots: 0,
    reviews: 0,
    metadata: 0,
  },
});

/**
 * Merge health/integrity payload with live pipeline KPIs (never show false zeros).
 */
export function reconcileIntegrityDisplay(integrity, kpis, stageResults) {
  try {
    const norm = normalizeIntegrityPayload(integrity, kpis, stageResults);
    const base = norm;
    const counts = { ...safeObj(base.table_counts) };
    const live = extractLiveKpis(norm.kpis, norm.stage_results);
    const canonical = safeObj(base.canonical_kpis);
    const accumulated = safeObj(base.accumulated_kpis);
    const authoritative = safeObj(base.authoritative_kpis);
    let reconciled = !!base.integrity_reconciled;
    const lineage = { ...safeLineage(base.kpi_lineage) };

    const kgEdges = stageMetric(norm.stage_results, "knowledge_graph", "total_edges");
    const kgNodes = stageMetric(norm.stage_results, "knowledge_graph", "total_nodes");
    const fusionSignals = stageMetric(norm.stage_results, "fusion", "signals_generated", "fusion.signals_generated");

    for (const [liveKey, countKey] of Object.entries(COUNT_KEYS)) {
      const dbVal = safeNum(counts[countKey]);
      const liveVal = safeNum(live[liveKey]);
      const canonVal = safeNum(
        canonical[liveKey] ?? accumulated[liveKey] ?? authoritative[liveKey],
      );
      const stageVal =
        liveKey === "graph_edges" ? kgEdges
          : liveKey === "graph_nodes" ? kgNodes
            : liveKey === "signals" ? fusionSignals
              : 0;

      const mergedVal = maxPos(
        [dbVal, "postgres"],
        [liveVal, "runtime"],
        [canonVal, "canonical_kpis"],
        [stageVal, "stage_results"],
      );

      if (mergedVal.value > dbVal) reconciled = true;
      counts[countKey] = mergedVal.value;
      const entry = {
        ...(lineage[countKey] || {}),
        source: mergedVal.source,
        postgres: dbVal,
        runtime: liveVal,
        canonical_kpis: canonVal,
        stage_results: stageVal,
        authoritative: mergedVal.value,
        reconciled: mergedVal.value > dbVal,
      };
      if (liveKey === "graph_edges") {
        entry.graph_edges_source = mergedVal.source;
      }
      lineage[countKey] = entry;
    }

    const reviews = safeNum(counts.reviews);
    const metadata = safeNum(counts.review_intelligence);
    const cov = { ...safeObj(base.coverage) };

    if (reviews > 0) {
      cov.metadata_coverage_pct = Math.round((metadata / reviews) * 1000) / 10;
    } else if (metadata > 0) {
      cov.metadata_coverage_pct = 100;
    }

    const graphNodes = safeNum(counts.graph_nodes);
    const graphEdges = safeNum(counts.graph_edges);
    const signals = safeNum(counts.fusion_signals);

    const fusionStage = safeStage(norm.stage_results, "fusion");
    const enrichmentWarning = !!(
      fusionStage.enrichment_warning
      && fusionStage.fusion_status === "completed"
      && signals > 0
    );

    const coreOperationalHealthy = signals > 0 && graphEdges > 0 && graphNodes > 0;

    const hasData =
      reviews > 0 ||
      metadata > 0 ||
      graphNodes > 0 ||
      graphEdges > 0 ||
      signals > 0;

    const status = base.status;
    const unavailable = status === "unavailable" || status === "unknown";

    const partial = !!norm.partial && !coreOperationalHealthy;

    return {
      table_counts: counts,
      coverage: cov,
      integrity_reconciled: reconciled || coreOperationalHealthy,
      runtime_authoritative: Object.values(live).some((v) => v > 0),
      integrity_consistent: base.integrity_consistent !== false && (coreOperationalHealthy || !hasData),
      kpi_lineage: lineage,
      hasData,
      unavailable,
      partial,
      safe_fallback: false,
      core_operational_healthy: coreOperationalHealthy,
      enrichment_warning: enrichmentWarning,
      display: {
        metadataCoveragePct: cov.metadata_coverage_pct,
        graphNodes,
        graphEdges,
        graphEntities: graphNodes + graphEdges,
        signals,
        anomalies: safeNum(counts.anomaly_events),
        snapshots: safeNum(counts.metric_snapshots),
        reviews,
        metadata,
      },
    };
  } catch (err) {
    bump("recoveries");
    logRecon("RECONCILIATION_SAFE", { fn: "reconcileIntegrityDisplay", error: String(err?.message || err) });
    return {
      ...EMPTY_DISPLAY,
      error: String(err?.message || err),
    };
  }
}

/** Alias for UI — always returns a display-safe object. */
export function reconcileIntegrityDisplaySafe(integrity, kpis, stageResults) {
  const out = reconcileIntegrityDisplay(integrity, kpis, stageResults);
  if (!out?.display || !isRecord(out.display)) {
    return { ...EMPTY_DISPLAY, safe_fallback: true };
  }
  return out;
}

export function formatCoveragePct(v) {
  if (typeof v === "number" && Number.isFinite(v)) return `${v}%`;
  return "—";
}

export function formatMetricCount(n) {
  const v = safeNum(n);
  try {
    return v.toLocaleString();
  } catch {
    return String(v);
  }
}
