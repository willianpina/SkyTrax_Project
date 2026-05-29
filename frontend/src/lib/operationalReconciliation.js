/** KPI-driven operational UI reconciliation — active run only, no stale degraded. */

function safeNum(v) {
  return typeof v === "number" && isFinite(v) ? v : 0;
}

function safeObj(v) {
  return v && typeof v === "object" && !Array.isArray(v) ? v : {};
}

/** Only events belonging to the active pipeline run. */
export function filterEventsForRun(events, operationId) {
  const list = Array.isArray(events) ? events : [];
  if (!operationId) return list;
  return list.filter((ev) => !ev?.operation_id || ev.operation_id === operationId);
}

/** Derive failed stages from KPIs + reconciled flags (never show impossible failures). */
export function effectiveFailedStages(failedStages, stageResults, kpis, integrity) {
  const failed = new Set(Array.isArray(failedStages) ? failedStages : []);
  const results = safeObj(stageResults);
  const counts = safeObj(integrity?.table_counts);

  const signals = Math.max(
    safeNum(kpis?.signals),
    safeNum(counts.fusion_signals),
    safeNum(results.fusion?.["fusion.signals_generated"]),
    safeNum(results.fusion?.signals_generated),
  );
  const metadata = Math.max(
    safeNum(kpis?.metadata),
    safeNum(counts.review_intelligence),
    safeNum(results.metadata?.metadata_total),
  );
  const graphNodes = Math.max(
    safeNum(kpis?.graph_nodes),
    safeNum(counts.graph_nodes),
    safeNum(results.knowledge_graph?.total_nodes),
  );

  for (const [stage, blob] of Object.entries(results)) {
    if (safeObj(blob).reconciled || safeObj(blob).degraded_classification === "false_degraded_stale_status") {
      failed.delete(stage);
    }
  }

  const fusionBlob = safeObj(results.fusion);
  if (
    fusionBlob.fusion_status === "completed"
    && (fusionBlob.enrichment_warning || fusionBlob.stage_warning)
    && !fusionBlob.correlation_failed
  ) {
    failed.delete("fusion");
  }

  if (signals > 0) failed.delete("fusion");
  if (metadata > 0) failed.delete("metadata");
  if (graphNodes > 0) failed.delete("knowledge_graph");

  const aviation = safeObj(results.aviation_master);
  if (aviation.reconciled) failed.delete("aviation_master");

  return [...failed];
}

/** Fusion completed with optional enrichment warning only — not a failed stage. */
export function isOptionalEnrichmentWarning(stageKey, stageResult) {
  const blob = safeObj(stageResult);
  return (
    stageKey === "fusion"
    && blob.fusion_status === "completed"
    && !!blob.enrichment_warning
    && !blob.correlation_failed
    && safeNum(blob.signals_generated) > 0
  );
}

/** Whether stage should display as failed in the UI. */
export function activeStageValidation(stageKey, failedStages, stageResults, kpis, integrity) {
  if (isOptionalEnrichmentWarning(stageKey, stageResults?.[stageKey])) {
    return "warning";
  }
  const effective = effectiveFailedStages(failedStages, stageResults, kpis, integrity);
  if (!effective.includes(stageKey)) return "ok";
  const blob = safeObj(stageResults?.[stageKey]);
  if (blob.reconciled) return "reconciled";
  return "failed";
}

/** Hint text derived from live KPIs — not stale linkage fallbacks. */
export function stageDegradedHint(stageKey, stageResult, kpis, integrity, t) {
  const blob = safeObj(stageResult);
  if (!blob || Object.keys(blob).length === 0) return "";

  if (blob.reconciled || blob.degraded_classification === "false_degraded_stale_status") {
    if (stageKey === "aviation_master") {
      return t("command:ops.linkage.aviation_reconciled", {
        defaultValue: "Aviation runtime reconciled — stale degraded status cleared",
      });
    }
    if (stageKey === "fusion") {
      return t("command:ops.linkage.fusion_reconciled", {
        defaultValue: "Fusion signals available — stale unavailable status cleared",
      });
    }
    return t("command:ops.linkage.stage_reconciled", {
      defaultValue: "Stage recovered — stale operational status reconciled",
    });
  }

  if (blob.dependency_contract_failed && blob.reason) {
    const signals = Math.max(safeNum(kpis?.signals), safeNum(integrity?.table_counts?.fusion_signals));
    if (stageKey === "fusion" && signals > 0) {
      return t("command:ops.linkage.fusion_reconciled", {
        defaultValue: "Fusion signals available — stale unavailable status cleared",
      });
    }
    return blob.reason;
  }

  const signals = Math.max(
    safeNum(kpis?.signals),
    safeNum(integrity?.table_counts?.fusion_signals),
    safeNum(blob.signals_generated),
  );
  const graphNodes = Math.max(
    safeNum(kpis?.graph_nodes),
    safeNum(integrity?.table_counts?.graph_nodes),
  );
  const metadata = Math.max(
    safeNum(kpis?.metadata),
    safeNum(integrity?.table_counts?.review_intelligence),
  );
  const graphEdges = Math.max(
    safeNum(kpis?.graph_edges),
    safeNum(integrity?.table_counts?.graph_edges),
  );

  if (
    isOptionalEnrichmentWarning(stageKey, blob)
    || (stageKey === "fusion" && blob.fusion_status === "completed" && signals > 0 && blob.enrichment_warning)
  ) {
    return t("command:ops.linkage.fusion_completed", {
      defaultValue: "Correlação semântica concluída",
    });
  }

  if (blob.stage_warning && blob.warning_type === "optional_enrichment_timeout") {
    return t("command:ops.linkage.fusion_enrichment_warning", {
      defaultValue: "Enriquecimento de aviação parcial",
    });
  }

  if (blob.degraded_classification === "aviation_enrichment_partial" && signals > 0) {
    return t("command:ops.linkage.fusion_completed", {
      defaultValue: "Correlação semântica concluída",
    });
  }

  if (!blob.error) return "";

  const err = String(blob.error);

  if (/upstream_not_ready|enrichment timeout|aviation enrichment/i.test(err) && signals > 0) {
    return t("command:ops.linkage.fusion_reconciled", {
      defaultValue: "Correlação semântica operacional — sinais disponíveis",
    });
  }
  if (/upstream_not_ready/i.test(err) && graphNodes > 0 && metadata > 0) {
    return t("command:ops.linkage.fusion_reconciled", {
      defaultValue: "Grafo e metadados presentes — status upstream reconciliado",
    });
  }

  if (/uniqueviolation|duplicate key/i.test(err) && /slug|airline_metadata_slug/i.test(err)) {
    return t("command:ops.linkage.aviation_identity_conflict", {
      defaultValue:
        "Canonical aviation identity conflict reconciled — merged via MDM slug/resolver (not a schema drift)",
    });
  }

  if (stageKey === "fusion" && signals > 0) {
    return t("command:ops.linkage.fusion_reconciled", {
      defaultValue: "Fusion signals available — stale unavailable status cleared",
    });
  }
  if (stageKey === "knowledge_graph" && graphNodes > 0) {
    return "";
  }
  if (
    stageKey === "aviation_master" &&
    /iata_code|schema drift|UndefinedColumn/i.test(err) &&
    !/uniqueviolation|duplicate key/i.test(err)
  ) {
    return t("command:ops.linkage.aviation_master", {
      defaultValue: "Aviation master degraded — runtime/schema inconsistency detected",
    });
  }

  const key = `command:ops.linkage.${stageKey}`;
  const mapped = t(key, { defaultValue: "" });
  if (mapped && mapped !== key && /unavailable|indispon|vazio|empty|degraded/i.test(mapped)) {
    if (stageKey === "fusion" && signals > 0) return "";
    return mapped;
  }

  return err.slice(0, 120);
}

export function hasReconciledStages(status) {
  return Array.isArray(status?.reconciled_stages) && status.reconciled_stages.length > 0;
}

export function staleEventExpired(ev, operationId) {
  if (!operationId || !ev?.operation_id) return false;
  return ev.operation_id !== operationId;
}
