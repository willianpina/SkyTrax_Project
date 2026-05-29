import React, { useMemo } from "react";
import { Shield } from "lucide-react";
import {
  formatCoveragePct,
  formatMetricCount,
  reconcileIntegrityDisplaySafe,
} from "../../lib/integrityReconciliation";
import { ReconciliationErrorBoundary } from "./ReconciliationErrorBoundary";

function IntegrityKpiCard({ value, label, accent, title }) {
  return (
    <div className={`osm-intel-kpi osm-intel-kpi--${accent}`} title={title}>
      <span className="osm-intel-kpi-val">{value}</span>
      <span className="osm-intel-kpi-label">{label}</span>
    </div>
  );
}

function PipelineIntegrityStripInner({ integrity, kpis, stageResults, t }) {
  const reconciled = useMemo(
    () => reconcileIntegrityDisplaySafe(integrity, kpis, stageResults),
    [integrity, kpis, stageResults],
  );

  if (reconciled.unavailable && !reconciled.hasData) return null;

  const display = reconciled.display ?? {};
  const coreHealthy = reconciled.core_operational_healthy;
  const partial = (reconciled.partial || reconciled.safe_fallback) && !coreHealthy;
  const enrichmentWarning = reconciled.enrichment_warning;

  return (
    <section className="osm-intel-panel" aria-label={t("command:ops.integrity.title", { defaultValue: "Operational integrity" })}>
      <header className="osm-intel-panel-head">
        <div className="osm-intel-panel-title">
          <Shield size={13} className="osm-intel-panel-icon" />
          <span>{t("command:ops.integrity.title", { defaultValue: "Integridade operacional" })}</span>
        </div>
        <div className="osm-intel-panel-badges">
          {reconciled.runtime_authoritative && (
            <span className="osm-pbadge osm-pbadge--live" title={t("command:ops.integrity.liveBadge", { defaultValue: "Live runtime KPIs" })}>
              {t("command:ops.integrity.live", { defaultValue: "AO VIVO" })}
            </span>
          )}
          {reconciled.integrity_reconciled && (
            <span className="osm-pbadge osm-pbadge--sync" title={t("command:ops.integrity.reconciledBadge", { defaultValue: "Reconciled with Postgres/runtime" })}>
              {t("command:ops.integrity.reconciled", { defaultValue: "RECONCILIADO" })}
            </span>
          )}
          {partial && (
            <span className="osm-pbadge osm-pbadge--partial">
              {t("command:ops.integrity.partial", { defaultValue: "PARCIAL" })}
            </span>
          )}
        </div>
      </header>

      <div className="osm-intel-kpi-grid">
        <IntegrityKpiCard
          value={formatCoveragePct(display.metadataCoveragePct)}
          label={t("command:ops.integrity.metadataCoverage", { defaultValue: "Cobertura" })}
          accent="coverage"
        />
        <IntegrityKpiCard
          value={formatMetricCount(display.graphNodes)}
          label={t("command:ops.integrity.graphNodes", { defaultValue: "Nós" })}
          accent="nodes"
          title={t("command:ops.integrity.graphNodesHint", { defaultValue: "graph_nodes" })}
        />
        <IntegrityKpiCard
          value={formatMetricCount(display.graphEdges)}
          label={t("command:ops.integrity.graphEdges", { defaultValue: "Relações" })}
          accent="edges"
          title={
            reconciled.kpi_lineage?.graph_edges?.graph_edges_source
              ? `source: ${reconciled.kpi_lineage.graph_edges.graph_edges_source}`
              : undefined
          }
        />
        <IntegrityKpiCard
          value={formatMetricCount(display.signals)}
          label={t("command:ops.integrity.signals", { defaultValue: "Sinais" })}
          accent="signals"
        />
        <IntegrityKpiCard
          value={formatMetricCount(display.anomalies)}
          label={t("command:ops.integrity.anomalies", { defaultValue: "Anomalias" })}
          accent="anomalies"
        />
        <IntegrityKpiCard
          value={formatMetricCount(display.snapshots)}
          label={t("command:ops.integrity.snapshots", { defaultValue: "Snapshots" })}
          accent="snapshots"
        />
      </div>

      {enrichmentWarning && (
        <p className="osm-intel-panel-footnote">
          {t("command:ops.linkage.fusion_enrichment_warning", {
            defaultValue: "Enriquecimento de aviação parcial",
          })}
        </p>
      )}
    </section>
  );
}

export function PipelineIntegrityStrip(props) {
  const { t } = props;
  return (
    <ReconciliationErrorBoundary
      fallbackLabel={t?.("command:ops.integrity.fallback", {
        defaultValue: "Integrity metrics temporarily unavailable — live KPIs below remain authoritative.",
      })}
    >
      <PipelineIntegrityStripInner {...props} />
    </ReconciliationErrorBoundary>
  );
}
