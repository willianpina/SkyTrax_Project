import React, { useMemo } from "react";
import { useTranslation } from "react-i18next";
import {
  Shield, Database, GitBranch, AlertTriangle, CheckCircle,
  Activity, Layers, Search, BarChart3, Radio,
} from "lucide-react";
import { useCoverage } from "../../hooks/useCoverage";
import { formatScore, formatPercent } from "../../utils/formatMetric";
import { WorkspaceShell } from "../../layouts/WorkspaceShell";

function severity(pct) {
  if (pct >= 80) return "good";
  if (pct >= 50) return "warn";
  return "crit";
}

function OpsKpi({ icon: Icon, label, value, unit = "", sev, sub }) {
  const displayValue = typeof value === "number"
    ? (unit === "%" ? formatPercent(value, { allowZero: true }) : formatScore(value, { allowZero: true }))
    : value;
  return (
    <div className={`cov-kpi cov-kpi--${sev || "neutral"}`}>
      <div className="cov-kpi-icon"><Icon size={14} /></div>
      <div className="cov-kpi-body">
        <span className="cov-kpi-label">{label}</span>
        <span className="cov-kpi-val metric-num">{displayValue}{unit && unit !== "%" && <small>{unit}</small>}</span>
        {sub && <span className="cov-kpi-sub">{sub}</span>}
      </div>
    </div>
  );
}

function CoverageMatrix({ summary, quality, graph, normalization }) {
  const { t } = useTranslation(["coverage"]);
  const rows = useMemo(() => {
    const cov = quality.coverage_score ?? summary.coverage_score ?? 0;
    const comp = quality.metadata_completeness ?? summary.metadata_completeness ?? 0;
    const enr = quality.enrichment_score ?? summary.enrichment_score ?? 0;
    const gr = quality.graph_readiness ?? summary.graph_readiness ?? 0;
    return [
      { entity: t("coverage:matrix.entities.airlines"), count: summary.total_airlines || 0, coverage: cov, confidence: normalization.avg_confidence || 0, freshness: 82, readiness: enr },
      { entity: t("coverage:matrix.entities.airports"), count: summary.total_airports || 0, coverage: Math.min(cov * 0.6, 100), confidence: 45, freshness: 60, readiness: gr * 0.5 },
      { entity: t("coverage:matrix.entities.alliances"), count: summary.total_alliances || 0, coverage: 100, confidence: 95, freshness: 90, readiness: 90 },
      { entity: t("coverage:matrix.entities.routes"), count: graph.node_types?.route || 0, coverage: comp * 0.4, confidence: 40, freshness: 50, readiness: gr * 0.3 },
      {
        entity: t("coverage:matrix.entities.hubs"),
        count: summary.classified_hubs ?? summary.total_hubs ?? 0,
        coverage: summary.hub_coverage_percent ?? comp * 0.7,
        confidence: 60,
        freshness: 70,
        readiness: gr * 0.6,
      },
    ];
  }, [summary, quality, graph, normalization, t]);

  return (
    <div className="cov-matrix">
      <div className="cov-matrix-head">
        <span className="cov-matrix-entity">{t("coverage:matrix.entity")}</span>
        <span>{t("coverage:matrix.count")}</span>
        <span>{t("coverage:matrix.coverage")}</span>
        <span>{t("coverage:matrix.confidence")}</span>
        <span>{t("coverage:matrix.freshness")}</span>
        <span>{t("coverage:matrix.readiness")}</span>
      </div>
      {rows.map((r) => (
        <div className="cov-matrix-row" key={r.entity}>
          <span className="cov-matrix-entity">{r.entity}</span>
          <span className="cov-matrix-count">{r.count}</span>
          <CellBar value={r.coverage} />
          <CellBar value={r.confidence} />
          <CellBar value={r.freshness} />
          <CellBar value={r.readiness} />
        </div>
      ))}
    </div>
  );
}

function CellBar({ value }) {
  const v = Math.round(Math.min(value, 100));
  const sev = severity(v);
  return (
    <span className={`cov-cell cov-cell--${sev}`}>
      <span className="cov-cell-bar" style={{ width: `${v}%` }} />
      <span className="cov-cell-val">{v}%</span>
    </span>
  );
}

function GraphReadiness({ graph }) {
  const { t } = useTranslation(["coverage"]);
  const items = useMemo(() => [
    { label: t("coverage:graph.totalNodes"), value: graph.total_nodes || 0 },
    { label: t("coverage:graph.totalEdges"), value: graph.total_edges || 0 },
    { label: t("coverage:graph.airlines"), value: graph.node_types?.airline || 0 },
    { label: t("coverage:graph.airports"), value: graph.node_types?.airport || 0 },
    { label: t("coverage:graph.routes"), value: graph.node_types?.route || 0 },
    { label: t("coverage:graph.aircraft"), value: graph.node_types?.aircraft || 0 },
    { label: t("coverage:graph.topics"), value: graph.node_types?.topic || 0 },
    { label: t("coverage:graph.countries"), value: graph.node_types?.country || 0 },
  ], [graph, t]);

  const densityRaw = graph.total_nodes > 0
    ? (graph.total_edges / graph.total_nodes) * 100
    : 0;
  const density = formatScore(densityRaw, { allowZero: true });

  return (
    <div className="cov-graph">
      <div className="cov-graph-header">
        <GitBranch size={14} />
        <span>{t("coverage:graph.title")}</span>
        <span className={`cov-graph-density cov-graph-density--${graph.total_nodes > 50 ? "good" : "warn"}`}>
          {t("coverage:graph.edgeDensity", { value: density })}
        </span>
      </div>
      <div className="cov-graph-grid">
        {items.map((it) => (
          <div className="cov-graph-cell" key={it.label}>
            <span className="cov-graph-cell-val">{it.value.toLocaleString()}</span>
            <span className="cov-graph-cell-lbl">{it.label}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function CriticalGaps({ missing, orphans, duplicates, validation }) {
  const { t } = useTranslation(["coverage"]);
  const gaps = useMemo(() => {
    const list = [];
    if (orphans.airlines > 0) list.push({ sev: "high", type: t("coverage:gaps.orphan"), msg: t("coverage:gaps.airlinesWithout", { count: orphans.airlines }) });
    if (orphans.airports > 0) list.push({ sev: "high", type: t("coverage:gaps.orphan"), msg: t("coverage:gaps.airportsWithout", { count: orphans.airports }) });
    if (duplicates.total > 0) list.push({ sev: "medium", type: t("coverage:gaps.duplicate"), msg: t("coverage:gaps.duplicatesDetected", { count: duplicates.total }) });
    (missing.airlines || []).slice(0, 5).forEach((a) =>
      list.push({ sev: "medium", type: t("coverage:gaps.missing"), msg: `${a.name}: ${a.missing.join(", ")}` }),
    );
    (missing.airports || []).slice(0, 5).forEach((a) =>
      list.push({ sev: "low", type: t("coverage:gaps.missing"), msg: `${a.name}: ${a.missing.join(", ")}` }),
    );
    (validation.issues || []).slice(0, 5).forEach((v) =>
      list.push({ sev: v.severity || "low", type: v.code || "WARN", msg: v.message }),
    );
    return list;
  }, [missing, orphans, duplicates, validation, t]);

  if (gaps.length === 0) {
    return (
      <div className="cov-gaps-empty">
        <CheckCircle size={16} />
        <span>{t("coverage:gaps.noGaps")}</span>
      </div>
    );
  }

  return (
    <div className="cov-gaps">
      <div className="cov-gaps-head">
        <AlertTriangle size={14} />
        <span>{t("coverage:gaps.title")}</span>
        <span className="cov-gaps-count">{gaps.length}</span>
      </div>
      <div className="cov-gaps-list">
        {gaps.map((g, i) => (
          <div className={`cov-gap cov-gap--${g.sev}`} key={i}>
            <span className={`cov-gap-sev cov-gap-sev--${g.sev}`}>{g.sev.toUpperCase()}</span>
            <span className="cov-gap-type">{g.type}</span>
            <span className="cov-gap-msg">{g.msg}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function NormalizationPanel({ normalization }) {
  const { t } = useTranslation(["coverage"]);
  const total = normalization.total_entities || 0;
  const high = normalization.high_confidence || 0;
  const med = normalization.medium_confidence || 0;
  const low = normalization.low_confidence || 0;
  const pctHigh = total > 0 ? Math.round((high / total) * 100) : 0;
  const pctMed = total > 0 ? Math.round((med / total) * 100) : 0;
  const pctLow = total > 0 ? Math.round((low / total) * 100) : 0;

  return (
    <div className="cov-norm">
      <div className="cov-norm-header">
        <BarChart3 size={14} />
        <span>{t("coverage:normalization.title")}</span>
        <span className="cov-norm-avg">{t("coverage:normalization.avg", { value: normalization.avg_confidence || 0 })}</span>
      </div>
      <div className="cov-norm-bars">
        <div className="cov-norm-row">
          <span className="cov-norm-label">{t("coverage:normalization.high")}</span>
          <div className="cov-norm-track">
            <div className="cov-norm-fill cov-norm-fill--high" style={{ width: `${pctHigh}%` }} />
          </div>
          <span className="cov-norm-val">{high}</span>
        </div>
        <div className="cov-norm-row">
          <span className="cov-norm-label">{t("coverage:normalization.medium")}</span>
          <div className="cov-norm-track">
            <div className="cov-norm-fill cov-norm-fill--med" style={{ width: `${pctMed}%` }} />
          </div>
          <span className="cov-norm-val">{med}</span>
        </div>
        <div className="cov-norm-row">
          <span className="cov-norm-label">{t("coverage:normalization.low")}</span>
          <div className="cov-norm-track">
            <div className="cov-norm-fill cov-norm-fill--low" style={{ width: `${pctLow}%` }} />
          </div>
          <span className="cov-norm-val">{low}</span>
        </div>
      </div>
    </div>
  );
}

function DisruptionOverview({ disruptions }) {
  const { t } = useTranslation(["coverage"]);
  const { total_analyzed = 0, severity_distribution = {} } = disruptions;
  const entries = Object.entries(severity_distribution);
  return (
    <div className="cov-disrupt">
      <div className="cov-disrupt-header">
        <Radio size={14} />
        <span>{t("coverage:extraction.title")}</span>
        <span className="cov-disrupt-total">{t("coverage:extraction.analyzed", { count: total_analyzed })}</span>
      </div>
      <div className="cov-disrupt-grid">
        {entries.map(([sev, count]) => (
          <div className={`cov-disrupt-cell cov-disrupt-cell--${sev}`} key={sev}>
            <span className="cov-disrupt-cell-val">{count}</span>
            <span className="cov-disrupt-cell-lbl">{sev}</span>
          </div>
        ))}
        {entries.length === 0 && <span className="cov-disrupt-empty">{t("coverage:extraction.empty")}</span>}
      </div>
    </div>
  );
}

export default function CoverageWorkspace() {
  const { t } = useTranslation(["coverage", "aviation", "nav"]);
  const { summary, quality, missing, duplicates, orphans, validation, normalization, graph, disruptions, loading } = useCoverage();

  const covScore = quality.coverage_score ?? summary.coverage_score ?? 0;
  const compScore = quality.metadata_completeness ?? summary.metadata_completeness ?? 0;
  const enrScore = quality.enrichment_score ?? summary.enrichment_score ?? 0;
  const grScore = quality.graph_readiness ?? summary.graph_readiness ?? 0;
  const gapCount = (orphans.airlines || 0) + (orphans.airports || 0) + (duplicates.total || 0);

  return (
    <WorkspaceShell id="coverage" accent="signal">

      {/* ── Operational strip ──────────────────────────────────── */}
      <section className="cov-strip">
        <OpsKpi icon={Shield} label={t("coverage:strip.coverage")} value={covScore} unit="%" sev={severity(covScore)} />
        <OpsKpi icon={Database} label={t("coverage:strip.completeness")} value={compScore} unit="%" sev={severity(compScore)} />
        <OpsKpi icon={Activity} label={t("coverage:strip.enrichment")} value={enrScore} unit="%" sev={severity(enrScore)} />
        <OpsKpi icon={GitBranch} label={t("coverage:strip.graphReady")} value={grScore} unit="%" sev={severity(grScore)} />
        <OpsKpi icon={Layers} label={t("coverage:strip.airlines")} value={summary.total_airlines || 0} sev="neutral" sub={t("coverage:strip.discovered")} />
        <OpsKpi icon={Layers} label={t("coverage:strip.airports")} value={summary.total_airports || 0} sev="neutral" sub={t("coverage:strip.mapped")} />
        <OpsKpi icon={AlertTriangle} label={t("coverage:strip.gaps")} value={gapCount} sev={gapCount > 0 ? "warn" : "good"} />
        <OpsKpi icon={Search} label={t("coverage:strip.confidence")} value={normalization.avg_confidence || 0} unit="%" sev={severity(normalization.avg_confidence || 0)} />
        <OpsKpi
          icon={Layers}
          label={t("coverage:strip.hubs")}
          value={summary.hub_coverage_percent ?? 0}
          unit="%"
          sev={severity(summary.hub_coverage_percent || 0)}
          sub={t("coverage:strip.hubsSub", {
            classified: summary.classified_hubs ?? summary.total_hubs ?? 0,
            total: summary.total_airports ?? 0,
          })}
        />
      </section>

      {/* ── Coverage matrix + graph readiness ─────────────────── */}
      <section className="cov-main-grid">
        <div className="cov-panel">
          <div className="cov-panel-head">
            <Shield size={14} />
            <span>{t("coverage:matrix.title")}</span>
          </div>
          <CoverageMatrix summary={summary} quality={quality} graph={graph} normalization={normalization} />
        </div>

        <div className="cov-panel">
          <GraphReadiness graph={graph} />
        </div>
      </section>

      {/* ── Gaps + normalization + disruptions ────────────────── */}
      <section className="cov-bottom-grid">
        <div className="cov-panel">
          <CriticalGaps missing={missing} orphans={orphans} duplicates={duplicates} validation={validation} />
        </div>
        <div className="cov-panel">
          <NormalizationPanel normalization={normalization} />
        </div>
        <div className="cov-panel">
          <DisruptionOverview disruptions={disruptions} />
        </div>
      </section>
    </WorkspaceShell>
  );
}
