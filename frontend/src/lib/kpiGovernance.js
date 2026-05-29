/** Canonical KPI governance — accumulated vs delta, graph nodes/edges semantics. */

import { isRecord, safeNum, safeObj } from "./integrityReconciliation.js";

function stageBlob(stageResults, stage) {
  return safeObj(isRecord(stageResults) ? stageResults[stage] : undefined);
}

/**
 * Resolve operational KPIs for UI (single source of truth).
 * @param {{ kpis?: object, integrity?: object, stageResults?: object }} input
 */
export function resolveOperationalKpis({ kpis = {}, integrity = {}, stageResults = {} } = {}) {
  const k = safeObj(kpis);
  const sr = safeObj(stageResults);
  const acc = safeObj(integrity?.accumulated_kpis || integrity?.canonical_kpis);
  const delta = safeObj(integrity?.delta_kpis);
  const gov = safeObj(integrity?.kpi_governance);
  const graphSem = safeObj(gov.graph_semantics);
  const avSem = safeObj(gov.aviation_semantics);

  const graphNodes = maxPos(
    k.graph_nodes,
    acc.graph_nodes,
    graphSem.nodes,
    stageBlob(sr, "knowledge_graph").total_nodes,
  );
  const graphEdges = maxPos(
    k.graph_edges,
    acc.graph_edges,
    graphSem.edges,
    stageBlob(sr, "knowledge_graph").total_edges,
  );

  const aviation = {
    total: maxPos(
      acc.aviation_metadata_total,
      avSem.total,
      stageBlob(sr, "aviation_master").airlines_total,
    ),
    linkedTotal: maxPos(
      acc.aviation_linked_total,
      avSem.linked_total,
      stageBlob(sr, "aviation_master").airlines_linked_total,
    ),
    processedThisRun: maxPos(
      delta.aviation_processed_this_run,
      avSem.processed_this_run,
      stageBlob(sr, "aviation_master").airlines_processed_this_run,
      (safeNum(stageBlob(sr, "aviation_master").airlines_created) +
        safeNum(stageBlob(sr, "aviation_master").airlines_updated)),
    ),
    linkedThisRun: maxPos(
      delta.aviation_linked_this_run,
      avSem.linked_this_run,
      stageBlob(sr, "aviation_master").links_created,
    ),
  };

  return {
    reviews: maxPos(k.reviews, acc.reviews),
    metadata: maxPos(k.metadata, acc.metadata),
    graphNodes,
    graphEdges,
    graphEntities: graphNodes + graphEdges,
    signals: maxPos(k.signals, acc.signals),
    anomalies: maxPos(k.anomalies, acc.anomalies),
    clusters: maxPos(k.clusters, acc.clusters),
    snapshots: maxPos(k.snapshots, acc.snapshots),
    aviation,
    divergences: Array.isArray(gov.divergences) ? gov.divergences : [],
    graphSemantics: {
      nodes: graphNodes,
      edges: graphEdges,
      entitiesSum: graphNodes + graphEdges,
      note: gov.graph_semantics?.note || "nodes and edges are separate canonical metrics",
    },
  };
}

function maxPos(...vals) {
  let best = 0;
  for (const v of vals) {
    const n = safeNum(v);
    if (n > best) best = n;
  }
  return best;
}

/** Format aviation stage throughput: delta vs accumulated (i18n). */
export function formatAviationThroughput(stageResult, authoritative, t) {
  const blob = safeObj(stageResult);
  const av = authoritative?.aviation || {};
  const total = safeNum(av.total);
  const linkedTotal = safeNum(av.linkedTotal);
  const run = safeNum(av.processedThisRun || blob.airlines_processed_this_run);
  const linkedRun = safeNum(av.linkedThisRun || blob.links_created);
  const tr = (key, opts) => t(`command:ops.throughput.${key}`, opts);

  if (total > 0) {
    return tr("aviationFull", {
      total: total.toLocaleString("pt-BR"),
      linked: linkedTotal.toLocaleString("pt-BR"),
      run: run.toLocaleString("pt-BR"),
    });
  }
  if (run > 0 || linkedRun > 0) {
    return tr("aviationRun", {
      run: run.toLocaleString("pt-BR"),
      linked: linkedRun.toLocaleString("pt-BR"),
    });
  }
  const created = safeNum(blob.airlines_created);
  const updated = safeNum(blob.airlines_updated);
  if (created || updated) {
    return tr("aviationDelta", { count: (created + updated).toLocaleString("pt-BR") });
  }
  return "";
}

/** Format graph for stage line (i18n). */
export function formatGraphThroughput(stageResult, authoritative, t) {
  const blob = safeObj(stageResult);
  const nodes = maxPos(authoritative?.graphNodes, blob.total_nodes);
  const edges = maxPos(authoritative?.graphEdges, blob.total_edges);
  if (nodes || edges) {
    return t("command:ops.throughput.graph", {
      nodes: nodes.toLocaleString("pt-BR"),
      edges: edges.toLocaleString("pt-BR"),
    });
  }
  return "";
}
