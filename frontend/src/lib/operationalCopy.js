/** Operational UX copy — executive PT-BR throughput and labels (via i18n). */

import { safeNum, safeObj } from "./integrityReconciliation.js";
import { formatAviationThroughput, formatGraphThroughput } from "./kpiGovernance.js";

function n(result, ...keys) {
  const blob = safeObj(result);
  for (const k of keys) {
    const v = blob[k];
    if (v !== undefined && v !== null) return safeNum(v);
  }
  return 0;
}

/**
 * Stage-level operational throughput (detailed) — always use with i18n `t`.
 */
export function formatStageThroughput(stageKey, result, authoritative, t) {
  if (!result || result.error) return "";
  const tr = (key, opts) => t(`command:ops.throughput.${key}`, opts);

  try {
    switch (stageKey) {
      case "discovery": {
        const count = n(result, "total_airlines_in_db", "airlines_discovered");
        return count > 0
          ? tr("airlinesDiscovered", { count: count.toLocaleString("pt-BR") })
          : tr("noneAirlines");
      }
      case "crawl": {
        const inserted = n(result, "reviews_inserted", "reviews_added");
        return inserted > 0
          ? tr("reviewsInserted", { count: inserted.toLocaleString("pt-BR") })
          : tr("noReviewsInserted");
      }
      case "metadata": {
        const total = n(result, "metadata_total", "reviews_analyzed");
        return total > 0
          ? tr("metadataRecords", { count: total.toLocaleString("pt-BR") })
          : tr("noMetadata");
      }
      case "semantic": {
        const enriched = n(result, "enriched");
        return enriched > 0
          ? tr("semanticEnriched", { count: enriched.toLocaleString("pt-BR") })
          : tr("noSemanticEnrichment");
      }
      case "knowledge_graph":
        return formatGraphThroughput(result, authoritative, t) || tr("graphEmpty");
      case "forecasting": {
        const fc = n(result, "forecasts_persisted");
        return fc > 0
          ? tr("forecasts", { count: fc.toLocaleString("pt-BR") })
          : tr("noForecasts");
      }
      case "anomalies": {
        const a = n(result, "anomalies_created");
        return a > 0
          ? tr("anomalies", { count: a.toLocaleString("pt-BR") })
          : tr("noAnomalies");
      }
      case "insights": {
        const ins = n(result, "insights_created", "insights_generated");
        return ins > 0
          ? tr("insights", { count: ins.toLocaleString("pt-BR") })
          : tr("noInsights");
      }
      case "fusion": {
        const sig = n(result, "fusion.signals_generated", "signals_generated");
        return sig > 0
          ? tr("signals", { count: sig.toLocaleString("pt-BR") })
          : tr("noSignals");
      }
      case "snapshots":
        return tr("snapshotsDone");
      case "aviation_master":
        return formatAviationThroughput(result, authoritative, t) || tr("aviationEmpty");
      case "airport_discovery": {
        const ap = n(result, "airports_in_db");
        return ap > 0
          ? tr("airports", { count: ap.toLocaleString("pt-BR") })
          : tr("noAirports");
      }
      case "aviation_metadata": {
        const al = n(result, "airlines_total");
        return al > 0
          ? tr("airlinesTotal", { count: al.toLocaleString("pt-BR") })
          : tr("noAirlines");
      }
      case "hub_intelligence": {
        const hubs = n(result, "active_hubs");
        return hubs > 0
          ? tr("hubs", { count: hubs.toLocaleString("pt-BR") })
          : tr("noHubs");
      }
      default:
        return "";
    }
  } catch {
    return "";
  }
}

/** Compact corpus line when integrity strip is hidden. */
export function formatCorpusSummary(reviews, metadata, t) {
  const tr = (key, opts) => t(`command:ops.corpusSummary.${key}`, opts);
  const parts = [];
  if (reviews > 0) parts.push(tr("reviews", { count: reviews.toLocaleString("pt-BR") }));
  if (metadata > 0) parts.push(tr("metadata", { count: metadata.toLocaleString("pt-BR") }));
  return parts.length ? parts.join(" · ") : tr("empty");
}
