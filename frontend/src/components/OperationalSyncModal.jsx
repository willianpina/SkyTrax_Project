import React, { memo, useMemo, useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import {
  X, CheckCircle, AlertTriangle, Loader2, Circle,
  Clock, Activity, Radio, Database, GitBranch, Zap,
  BarChart3, Layers, Search, Shield, TrendingUp,
  Globe, Cpu,
} from "lucide-react";
import { formatOperationalTime } from "../utils/datetime";
import { usePlatformHealth } from "../hooks/usePlatformHealth";
import {
  activeStageValidation,
  isOptionalEnrichmentWarning,
  effectiveFailedStages,
  filterEventsForRun,
  hasReconciledStages,
  stageDegradedHint,
} from "../lib/operationalReconciliation";
import { PipelineIntegrityStrip } from "./operations/PipelineIntegrityStrip";
import { ReconciliationErrorBoundary } from "./operations/ReconciliationErrorBoundary";
import { OperationalStatusBar } from "../design-system/components/OperationalStatusBar";
import { resolveOperationalKpis } from "../lib/kpiGovernance";
import { formatStageThroughput, formatCorpusSummary } from "../lib/operationalCopy";
import { reconcileIntegrityDisplaySafe } from "../lib/integrityReconciliation";

const FULL_STAGES = [
  { key: "discovery", icon: Search, descKey: "stageDesc.discovery" },
  { key: "crawl", icon: Globe, descKey: "stageDesc.crawl" },
  { key: "metadata", icon: Database, descKey: "stageDesc.metadata" },
  { key: "semantic", icon: Cpu, descKey: "stageDesc.semantic" },
  { key: "knowledge_graph", icon: GitBranch, descKey: "stageDesc.knowledgeGraph" },
  { key: "forecasting", icon: TrendingUp, descKey: "stageDesc.forecasting" },
  { key: "anomalies", icon: AlertTriangle, descKey: "stageDesc.anomalies" },
  { key: "insights", icon: Zap, descKey: "stageDesc.insights" },
  { key: "aviation_master", icon: Globe, descKey: "stageDesc.aviationMaster" },
  { key: "fusion", icon: Layers, descKey: "stageDesc.fusion" },
  { key: "snapshots", icon: BarChart3, descKey: "stageDesc.snapshots" },
];

const AVIATION_STAGES = [
  { key: "aviation_master", icon: Database, descKey: "stageDesc.aviationMaster" },
  { key: "airport_discovery", icon: Globe, descKey: "stageDesc.airportDiscovery" },
  { key: "aviation_metadata", icon: Database, descKey: "stageDesc.aviationMetadata" },
  { key: "hub_intelligence", icon: Shield, descKey: "stageDesc.hubIntelligence" },
];

/* ── Payload normalizer ─────────────────────────────────────── */
function safeNum(v) { return typeof v === "number" && isFinite(v) ? v : 0; }
function safeArr(v) { return Array.isArray(v) ? v : []; }
function safeObj(v) { return v && typeof v === "object" && !Array.isArray(v) ? v : {}; }
function safeStr(v) { return typeof v === "string" ? v : typeof v === "object" ? JSON.stringify(v) : String(v ?? ""); }

function normalizePayload(raw) {
  const s = safeObj(raw);
  return {
    running: !!s.running,
    stage: safeStr(s.stage || "idle"),
    progress: safeNum(s.progress),
    operation_id: safeStr(s.operation_id),
    pipeline_type: safeStr(s.pipeline_type || "full"),
    pipeline_status: safeStr(s.pipeline_status || ""),
    events: safeArr(s.events).map((e) => ({ time: safeStr(e?.time), message: safeStr(e?.message) })),
    active_layers: safeArr(s.active_layers),
    completed_stages: safeArr(s.completed_stages),
    failed_stages: safeArr(s.failed_stages),
    stage_results: safeObj(s.stage_results),
    kpis: safeObj(s.kpis),
    heartbeat: s.heartbeat ? safeObj(s.heartbeat) : null,
    crawl_telemetry: s.crawl_telemetry ? safeObj(s.crawl_telemetry) : null,
    updated_at: safeStr(s.updated_at),
    stall_diagnosis: safeObj(s.stall_diagnosis),
    heartbeat_age_s: safeNum(s.heartbeat_age_s ?? s.stale_seconds),
    worker_alive: s.worker_alive === true,
    stale: !!s.stale,
    busy_without_heartbeat: !!s.busy_without_heartbeat,
    started_at: safeStr(s.started_at),
    reconciled_stages: safeArr(s.reconciled_stages),
    reconciliation_status: safeStr(s.reconciliation_status),
    operational_consistency: safeObj(s.operational_consistency),
    integrity: safeObj(s.integrity),
  };
}

/* ── Governor state badge ───────────────────────────────────── */
function GovernorBadge({ telemetry, t }) {
  if (!telemetry) return null;
  const ct = safeObj(telemetry);
  const terminated = !!ct.governor_terminated;
  const trigger = safeStr(ct.termination_trigger).replace(/_/g, " ");
  const state = safeStr(ct.termination_state);
  const dupeStreak = safeNum(ct.duplicate_streak);
  const noInsertSec = safeNum(ct.no_insert_seconds);

  if (terminated) {
    return (
      <div className="osm-governor osm-governor--terminated">
        <Shield size={12} />
        <span>{t("command:ops.governor.terminated", { trigger })}</span>
      </div>
    );
  }
  if (state === "zombie") {
    return (
      <div className="osm-governor osm-governor--zombie">
        <AlertTriangle size={12} />
        <span>{t("command:ops.governor.zombie")}</span>
      </div>
    );
  }
  if (noInsertSec > 60) {
    return (
      <div className="osm-governor osm-governor--noprogress">
        <Clock size={12} />
        <span>{t("command:ops.governor.noProgress", { seconds: noInsertSec, streak: dupeStreak })}</span>
      </div>
    );
  }
  return null;
}

/* ── Stage resolution ───────────────────────────────────────── */
function resolveStages(status) {
  return status.pipeline_type === "aviation" ? AVIATION_STAGES : FULL_STAGES;
}

const PIPELINE_TERMINAL = new Set(["completed", "completed_degraded"]);

function stageState(stageKey, currentStage, completedStages, failedStages, stages, stageResults, kpis, integrity) {
  if (isOptionalEnrichmentWarning(stageKey, stageResults?.[stageKey])) return "done";
  const validation = activeStageValidation(stageKey, failedStages, stageResults, kpis, integrity);
  if (validation === "reconciled" || validation === "warning") return "done";
  if (validation === "failed" || failedStages.includes(stageKey)) return "failed";
  if (completedStages.includes(stageKey)) return "done";
  if (PIPELINE_TERMINAL.has(currentStage)) return "done";
  const currentIdx = stages.findIndex((s) => s.key === currentStage);
  const stageIdx = stages.findIndex((s) => s.key === stageKey);
  if (currentStage === "failed") return stageIdx <= currentIdx ? "done" : "pending";
  if (currentStage === "starting") return "pending";
  if (stageIdx < currentIdx) return "done";
  if (stageIdx === currentIdx) return "active";
  return "pending";
}

function StageIcon({ state }) {
  switch (state) {
    case "done": return <CheckCircle size={12} className="si si--done" />;
    case "active": return <Loader2 size={12} className="spin si si--active" />;
    case "failed": return <AlertTriangle size={12} className="si si--error" />;
    default: return <Circle size={12} className="si si--pending" />;
  }
}

function progressColor(progress, stage) {
  if (stage === "failed") return "var(--ops-red)";
  if (stage === "stalled" || stage === "timeout") return "var(--ops-amber, #f59e0b)";
  if (stage === "completed_degraded") return "var(--ops-amber, #f59e0b)";
  if (stage === "completed") return "var(--ops-green)";
  if (progress < 15) return "var(--ops-blue)";
  return "var(--ops-cyan)";
}

function eventIcon(msg) {
  const m = (msg || "").toLowerCase();
  if (m.includes("degraded")) return <AlertTriangle size={10} className="ev-icon ev-icon--warn" />;
  if (m.includes("completed") || m.includes("done")) return <CheckCircle size={10} className="ev-icon ev-icon--done" />;
  if (m.includes("failed") || m.includes("error")) return <AlertTriangle size={10} className="ev-icon ev-icon--error" />;
  if (m.includes("saturat")) return <Zap size={10} className="ev-icon ev-icon--warn" />;
  if (m.includes("started") || m.includes("triggered")) return <Radio size={10} className="ev-icon ev-icon--active" />;
  if (m.includes("review") || m.includes("+")) return <Database size={10} className="ev-icon ev-icon--data" />;
  return <Clock size={10} className="ev-icon" />;
}

function fmtElapsed(s) {
  if (!s || s < 0) return "0s";
  const m = Math.floor(s / 60);
  const sec = Math.floor(s % 60);
  return m > 0 ? `${m}m ${sec}s` : `${sec}s`;
}

function normalizeEventTime(raw) {
  if (!raw) return formatOperationalTime();
  if (/^\d{2}:\d{2}:\d{2}$/.test(raw)) return raw;
  return formatOperationalTime(raw);
}

/* ── Professional event message translator ──────────────────── */
function translateEvent(raw, t) {
  const msg = (raw || "").trim();

  const durationMatch = msg.match(/\((\d+)ms\)/);
  const durationStr = durationMatch
    ? (parseInt(durationMatch[1]) >= 1000
        ? `${(parseInt(durationMatch[1]) / 1000).toFixed(1)}s`
        : `${durationMatch[1]}ms`)
    : null;

  const stageStarted = msg.match(/^Stage '([^']+)' started$/);
  if (stageStarted) {
    const stageKey = stageStarted[1].replace(/ /g, "_");
    const label = t(`command:ops.stages.${stageKey}`, { defaultValue: stageStarted[1] });
    return { text: t("command:ops.eventMessages.stageStarted", { stage: label }), duration: null };
  }

  const stageCompleted = msg.match(/^Stage '([^']+)' completed/);
  if (stageCompleted) {
    const stageKey = stageCompleted[1].replace(/ /g, "_");
    const label = t(`command:ops.stages.${stageKey}`, { defaultValue: stageCompleted[1] });
    return { text: t("command:ops.eventMessages.stageCompleted", { stage: label }), duration: durationStr };
  }

  const stageDegraded = msg.match(/^Stage '([^']+)' degraded/);
  if (stageDegraded) {
    const stageKey = stageDegraded[1].replace(/ /g, "_");
    const label = t(`command:ops.stages.${stageKey}`, { defaultValue: stageDegraded[1] });
    return { text: t("command:ops.eventMessages.stageDegraded", { stage: label, defaultValue: `${label} — degraded` }), duration: durationStr };
  }

  const stageFailed = msg.match(/^Stage '([^']+)' failed/);
  if (stageFailed) {
    const stageKey = stageFailed[1].replace(/ /g, "_");
    const label = t(`command:ops.stages.${stageKey}`, { defaultValue: stageFailed[1] });
    return { text: t("command:ops.eventMessages.stageFailed", { stage: label }), duration: durationStr };
  }

  if (/pipeline started/i.test(msg)) return { text: t("command:ops.eventMessages.pipelineStarted"), duration: null };
  if (/pipeline completed_degraded/i.test(msg)) return { text: t("command:ops.eventMessages.pipelineDegraded", { defaultValue: "Pipeline completed with degraded stages" }), duration: durationStr };
  if (/pipeline completed/i.test(msg)) return { text: t("command:ops.eventMessages.pipelineCompleted"), duration: durationStr };
  if (/pipeline failed/i.test(msg)) return { text: t("command:ops.eventMessages.pipelineFailed"), duration: durationStr };
  if (/pipeline triggered/i.test(msg)) return { text: t("command:ops.eventMessages.pipelineTriggered"), duration: null };
  if (/trend forecasting completed/i.test(msg)) return { text: t("command:ops.eventMessages.trendForecastingCompleted"), duration: durationStr };
  if (/correlation signals started/i.test(msg)) return { text: t("command:ops.eventMessages.correlationStarted"), duration: null };
  if (/correlation signals completed/i.test(msg)) return { text: t("command:ops.eventMessages.correlationCompleted"), duration: durationStr };
  if (/knowledge graph (built|completed)/i.test(msg)) return { text: t("command:ops.eventMessages.graphBuilt"), duration: durationStr };
  if (/semantic enrichment completed/i.test(msg)) return { text: t("command:ops.eventMessages.semanticCompleted"), duration: durationStr };
  if (/aviation sync started/i.test(msg)) return { text: t("command:ops.eventMessages.aviationSyncStarted"), duration: null };
  if (/aviation sync completed/i.test(msg)) return { text: t("command:ops.eventMessages.aviationSyncCompleted"), duration: durationStr };
  if (/aviation sync failed/i.test(msg)) return { text: t("command:ops.eventMessages.aviationSyncFailed"), duration: durationStr };
  if (/aviation sync triggered/i.test(msg)) return { text: t("command:ops.eventMessages.aviationSyncTriggered"), duration: null };
  if (/saturat/i.test(msg)) return { text: t("command:ops.eventMessages.corpusSaturated"), duration: null };
  if (/\[TERMINATION\]/i.test(msg) || /governor terminat/i.test(msg)) return { text: t("command:ops.eventMessages.governorTerminated", { defaultValue: "Subprocess terminated by governor" }), duration: null };
  if (/\[HARD_KILL\]/i.test(msg)) return { text: t("command:ops.eventMessages.hardKill", { defaultValue: "Hard kill — subprocess force-terminated" }), duration: null };
  if (/\[ZOMBIE\]/i.test(msg)) return { text: t("command:ops.eventMessages.zombie", { defaultValue: "Zombie subprocess detected" }), duration: null };
  if (/\[NO_PROGRESS\]/i.test(msg)) return { text: t("command:ops.eventMessages.noProgress", { defaultValue: "Subprocess running without progress" }), duration: null };
  if (/\[TELEMETRY_STATIC\]/i.test(msg)) return { text: t("command:ops.eventMessages.telemetryStatic", { defaultValue: "Telemetry frozen — no activity" }), duration: null };
  if (/\[CRAWL_EXIT\]/i.test(msg)) return { text: t("command:ops.eventMessages.crawlExit", { defaultValue: "Crawl process exited" }), duration: null };
  if (/\[REACTOR\]/i.test(msg)) return { text: t("command:ops.eventMessages.reactorHanging", { defaultValue: "Scrapy reactor hanging — terminating" }), duration: null };

  return { text: msg, duration: durationStr };
}

/* ── Animated counter ───────────────────────────────────────── */
function AnimatedCounter({ value }) {
  const [display, setDisplay] = useState(value);
  const prevRef = useRef(value);

  useEffect(() => {
    const prev = prevRef.current;
    if (prev === value) return;
    prevRef.current = value;
    if (typeof value !== "number" || typeof prev !== "number") { setDisplay(value); return; }
    const diff = value - prev;
    if (diff <= 0 || diff > 50000) { setDisplay(value); return; }
    const steps = Math.min(diff, 20);
    const perStep = diff / steps;
    let step = 0;
    const id = setInterval(() => {
      step++;
      setDisplay(Math.round(prev + perStep * step));
      if (step >= steps) clearInterval(id);
    }, 40);
    return () => clearInterval(id);
  }, [value]);

  return <>{typeof display === "number" ? display.toLocaleString() : display}</>;
}

/* ── CrawlIntel ─────────────────────────────────────────────── */
function CrawlIntel({ telemetry }) {
  const { t } = useTranslation(["command"]);
  if (!telemetry) return null;
  const ct = safeObj(telemetry);
  const current_airline = safeStr(ct.current_airline);
  const pages_processed = safeNum(ct.pages_processed);
  const reviews_added = safeNum(ct.reviews_added);
  const reviews_total = safeNum(ct.reviews_total);
  const duplicates_skipped = safeNum(ct.duplicates_skipped);
  const reviews_per_second = safeNum(ct.reviews_per_second);
  const elapsed_seconds = safeNum(ct.elapsed_seconds);
  const stalled = !!ct.stalled;
  const saturated = !!ct.saturated;
  const airlines_queued = safeNum(ct.airlines_queued);
  const pages_since_last_insert = safeNum(ct.pages_since_last_insert);

  return (
    <div className={`osm-crawl ${stalled ? "osm-crawl--stalled" : ""} ${saturated ? "osm-crawl--saturated" : ""}`}>
      {stalled && (
        <div className="osm-crawl-stall">
          <AlertTriangle size={12} />
          <span>{t("command:ops.crawlTelemetry.stalled")}</span>
        </div>
      )}
      {saturated && !stalled && (
        <div className="osm-crawl-saturated">
          <Zap size={12} />
          <span>{t("command:ops.crawlTelemetry.saturated", { count: pages_since_last_insert })}</span>
        </div>
      )}
      <div className="osm-crawl-header">
        <Globe size={12} />
        <span>{t("command:ops.crawlTelemetry.title")}</span>
        {current_airline && <span className="osm-crawl-target">{current_airline}</span>}
      </div>
      <div className="osm-crawl-grid">
        <div className="osm-crawl-cell">
          <span className="osm-crawl-val osm-crawl-val--lg"><AnimatedCounter value={reviews_total} /></span>
          <span className="osm-crawl-label">{t("command:ops.crawlTelemetry.corpusTotal")}</span>
        </div>
        <div className="osm-crawl-cell osm-crawl-cell--accent">
          <span className="osm-crawl-val osm-crawl-val--lg">+<AnimatedCounter value={reviews_added} /></span>
          <span className="osm-crawl-label">{t("command:ops.crawlTelemetry.newReviews")}</span>
        </div>
        <div className="osm-crawl-cell">
          <span className="osm-crawl-val"><AnimatedCounter value={pages_processed} /></span>
          <span className="osm-crawl-label">{t("command:ops.crawlTelemetry.pages")}</span>
        </div>
        <div className="osm-crawl-cell">
          <span className="osm-crawl-val"><AnimatedCounter value={duplicates_skipped} /></span>
          <span className="osm-crawl-label">{t("command:ops.crawlTelemetry.duplicates")}</span>
        </div>
        <div className="osm-crawl-cell">
          <span className="osm-crawl-val">{reviews_per_second}/s</span>
          <span className="osm-crawl-label">{t("command:ops.crawlTelemetry.throughput")}</span>
        </div>
        <div className="osm-crawl-cell">
          <span className="osm-crawl-val">{fmtElapsed(elapsed_seconds)}</span>
          <span className="osm-crawl-label">{t("command:ops.crawlTelemetry.elapsed")}</span>
        </div>
        <div className="osm-crawl-cell">
          <span className="osm-crawl-val">{airlines_queued}</span>
          <span className="osm-crawl-label">{t("command:ops.crawlTelemetry.airlines")}</span>
        </div>
        {reviews_per_second > 0 && (
          <div className="osm-crawl-cell">
            <span className="osm-crawl-val">~{fmtElapsed(Math.round((airlines_queued * 30) / Math.max(reviews_per_second, 0.1)))}</span>
            <span className="osm-crawl-label">{t("command:ops.crawlEstRemaining")}</span>
          </div>
        )}
      </div>
    </div>
  );
}

function platformBadgeVariant(severity) {
  if (severity === "warn") return "safe";
  if (severity === "info") return "forecast";
  if (severity === "error") return "error";
  return "neutral";
}

function OperationalSyncModalInner({ isOpen, onClose, status: rawStatus, history, onReset, onRetrySync }) {
  const { t } = useTranslation(["command", "common"]);
  const { badges: platformBadges, integrity: healthIntegrity } = usePlatformHealth(20000, {
    enabled: isOpen,
    pipelineOnly: true,
  });
  const eventsEndRef = useRef(null);

  const status = useMemo(() => normalizePayload(rawStatus), [rawStatus]);
  const stages = useMemo(() => resolveStages(status), [status]);
  const operationId = status.operation_id;
  const runEvents = useMemo(
    () => filterEventsForRun(status.events, operationId),
    [status.events, operationId],
  );
  const integrity = useMemo(() => {
    const embedded = safeObj(status.integrity?.table_counts ? status.integrity : rawStatus?.integrity);
    if (embedded.table_counts && Object.keys(embedded.table_counts).length) {
      return { ...healthIntegrity, ...embedded };
    }
    return healthIntegrity;
  }, [status.integrity, rawStatus?.integrity, healthIntegrity]);

  const failedStages = useMemo(
    () => effectiveFailedStages(status.failed_stages, status.stage_results, status.kpis, integrity),
    [status.failed_stages, status.stage_results, status.kpis, integrity],
  );
  const reconciled = hasReconciledStages(status);

  const stageResults = status.stage_results;
  const kpis = status.kpis;

  const authoritative = useMemo(
    () => resolveOperationalKpis({ kpis, integrity, stageResults }),
    [kpis, integrity, stageResults],
  );

  const integrityReconciled = useMemo(
    () => reconcileIntegrityDisplaySafe(integrity, kpis, stageResults),
    [integrity, kpis, stageResults],
  );

  const modalModel = useMemo(() => {
    const {
      stage,
      pipeline_type: pipelineType,
      pipeline_status: pipelineStatus,
      progress,
      completed_stages: completedStages,
      heartbeat: hb,
      crawl_telemetry: ct,
    } = status;

    const isDegraded = stage === "completed_degraded" && failedStages.length > 0;
    const isRunningDegraded = pipelineStatus === "running_degraded" && status.running;
    const isBusyWithoutHeartbeat = pipelineStatus === "busy_without_heartbeat" || !!status.busy_without_heartbeat;
    const isSlowFinalizing = ["running_slow", "busy_without_heartbeat", "finalizing", "persisting"].includes(pipelineStatus) || isBusyWithoutHeartbeat;
    const isStalled = (stage === "stalled" || stage === "timeout" || !!rawStatus?.stale) && !isSlowFinalizing;
    const isActive = (!isStalled && !isDegraded && (status.running || !["idle", "completed", "completed_degraded", "failed"].includes(stage)))
      || isSlowFinalizing;

    const failedCount = failedStages.length;
    const doneCount = stages.filter(
      (s) => stageState(s.key, stage, completedStages, failedStages, stages, stageResults, kpis, integrity) === "done",
    ).length;
    const computedProgress = PIPELINE_TERMINAL.has(stage) ? 100
      : stage === "idle" ? 0
      : isStalled ? progress
      : Math.max(progress, Math.round((doneCount / stages.length) * 100));

    const dig = (obj, ...keys) => {
      for (const k of keys) { const v = obj?.[k]; if (v !== undefined && v !== null) return safeNum(v); }
      return 0;
    };

    const kpiVal = (kpiKey, ...fallbacks) => {
      if (kpis?.[kpiKey] !== undefined && kpis?.[kpiKey] !== null) {
        return safeNum(kpis[kpiKey]);
      }
      for (const fb of fallbacks) {
        if (typeof fb === "number") return fb;
      }
      return 0;
    };

    const reviewsTotal = authoritative.reviews || kpiVal("reviews",
      safeNum(ct?.reviews_total),
      dig(stageResults?.crawl, "total_reviews_in_db", "reviews_total"),
    );
    const metadataCount = authoritative.metadata || kpiVal("metadata", dig(stageResults?.metadata, "reviews_analyzed"));

    let statusClass = "standby";
    let statusLabel = "standby";
    if (isStalled) { statusClass = "stalled"; statusLabel = "stalled"; }
    else if (isSlowFinalizing) {
      statusClass = "running";
      if (isBusyWithoutHeartbeat) statusLabel = "busy_without_heartbeat";
      else if (pipelineStatus === "persisting") statusLabel = "persisting";
      else if (pipelineStatus === "finalizing") statusLabel = "finalizing";
      else if (stage === "fusion" || hb?.stage_detail?.toLowerCase().includes("fusion")) statusLabel = "fusion_finalizing";
      else if (stage === "snapshots") statusLabel = "snapshot_finalizing";
      else statusLabel = "running_slow";
    } else if (isDegraded) { statusClass = "degraded"; statusLabel = "degraded"; }
    else if (isRunningDegraded) { statusClass = "degraded"; statusLabel = "running_degraded"; }
    else if (isActive) { statusClass = "running"; statusLabel = "synchronizing"; }
    else if (stage === "completed") { statusClass = "done"; statusLabel = "completed"; }
    else if (stage === "failed") { statusClass = "error"; statusLabel = "failed"; }
    if (ct?.governor_terminated && isActive) {
      statusClass = "terminated";
      statusLabel = "governor_terminated";
    } else if (ct?.termination_state === "zombie") {
      statusClass = "zombie";
      statusLabel = "zombie";
    } else if (ct?.saturated && isActive) {
      statusClass = "saturated";
      statusLabel = "saturated";
    } else if (ct?.no_insert_seconds > 60 && isActive && !ct?.saturated) {
      statusClass = "noprogress";
      statusLabel = "no_progress";
    }
    if (ct?.stalled && isActive && !ct?.saturated && !ct?.governor_terminated) {
      statusClass = "stalled";
      statusLabel = "crawl_stalled";
    }

    const showIntegrityStrip = !(integrityReconciled.unavailable && !integrityReconciled.hasData);
    const corpusSummary = formatCorpusSummary(reviewsTotal, metadataCount, t);

    return {
      stage,
      pipelineType,
      pipelineStatus,
      progress,
      completedStages,
      hb,
      ct,
      isDegraded,
      isRunningDegraded,
      isBusyWithoutHeartbeat,
      isSlowFinalizing,
      isStalled,
      isActive,
      failedCount,
      doneCount,
      computedProgress,
      reviewsTotal,
      metadataCount,
      showIntegrityStrip,
      corpusSummary,
      statusClass,
      statusLabel,
    };
  }, [
    status,
    failedStages,
    stages,
    integrity,
    integrityReconciled,
    authoritative,
    rawStatus?.stale,
    stageResults,
    kpis,
    t,
  ]);

  useEffect(() => {
    if (!isOpen) return;
    eventsEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [runEvents, isOpen]);

  if (!isOpen) return null;

  const {
    stage,
    pipelineType,
    pipelineStatus,
    progress,
    completedStages,
    hb,
    ct,
    isDegraded,
    isRunningDegraded,
    isBusyWithoutHeartbeat,
    isSlowFinalizing,
    isStalled,
    isActive,
    failedCount,
    doneCount,
    computedProgress,
    reviewsTotal,
    metadataCount,
    showIntegrityStrip,
    corpusSummary,
    statusClass,
    statusLabel,
  } = modalModel;

  const statusLabelResolved = (() => {
    switch (statusLabel) {
      case "stalled": return t("command:ops.stalled");
      case "busy_without_heartbeat": return t("command:ops.busyWithoutHeartbeat");
      case "persisting": return t("command:ops.persisting");
      case "finalizing": return t("command:ops.finalizing");
      case "fusion_finalizing": return t("command:ops.fusionFinalizing");
      case "snapshot_finalizing": return t("command:ops.snapshotFinalizing");
      case "running_slow": return t("command:ops.runningSlow");
      case "degraded": return t("command:ops.degraded", { count: failedCount });
      case "running_degraded": return t("command:ops.runningDegraded", { count: failedCount });
      case "synchronizing": return t("command:ops.synchronizing");
      case "completed": return t("command:ops.synchronized");
      case "failed": return t("command:ops.failed");
      case "governor_terminated": return t("command:ops.governorTerminated");
      case "zombie": return t("command:ops.zombie");
      case "saturated": return t("command:ops.saturated");
      case "no_progress": return t("command:ops.noProgress");
      case "crawl_stalled": return t("command:ops.crawlStalled");
      default:
        if (stage === "completed" || stage === "completed_degraded") return t("command:ops.pipelineCompleted");
        if (stage === "idle") return t("command:ops.monitoring");
        return t("command:ops.operational");
    }
  })();

  const bannerTitle = pipelineType === "aviation"
    ? t("command:ops.aviationSyncTitle")
    : t("command:ops.pipelineTitle", { defaultValue: "Plataforma Analítica Operacional" });
  const bannerSubtitle = pipelineType === "aviation"
    ? t("command:ops.aviationSyncSubtitle")
    : t("command:ops.pipelineSubtitle", {
        defaultValue: "Orquestração de inteligência, corpus e correlação semântica",
      });
  const statusBarItems = [
    {
      key: "sync-marker",
      kind: "primary",
      label: isActive ? "MONITORAMENTO ATIVO" : "SINCRONIZADO",
      severity: isActive ? "active" : "sync",
    },
    {
      key: "pipeline-status",
      kind: "secondary",
      label: statusLabelResolved,
      severity: statusClass,
      pulse: isActive,
    },
    ...platformBadges.map((badge) => ({
      key: `platform-${badge.key}`,
      kind: badge.severity === "error" ? "critical" : "secondary",
      label: badge.label,
      severity: badge.severity,
      title: badge.tooltip || badge.title || badge.key,
    })),
  ];

  return (
    <div className="osm-overlay" onClick={onClose}>
      <div className="osm osm--enterprise" onClick={(e) => e.stopPropagation()}>

        {/* ── Executive banner ─────────────────────────────────── */}
        <header className="osm-executive-banner">
          <div className="osm-banner-top">
            <div className="osm-banner-identity">
              <div className={`osm-banner-icon ${isActive ? "osm-banner-icon--active" : ""}`}>
                <Activity size={20} className={isActive ? "pulse-icon" : ""} />
              </div>
              <div className="osm-banner-copy">
                <h2 className="osm-banner-title">{bannerTitle}</h2>
                <p className="osm-banner-subtitle">{bannerSubtitle}</p>
              </div>
            </div>
            <button type="button" className="osm-close" onClick={onClose} aria-label="Close">
              <X size={16} />
            </button>
          </div>
          <OperationalStatusBar
            className="osm-banner-status-row"
            items={statusBarItems}
            renderItem={(item) => {
              if (item.kind === "primary") {
                return (
                  <span className={`osm-pbadge osm-pbadge--primary osm-pbadge--status osm-pbadge--status-${item.severity}`}>
                    {item.pulse && <span className="osm-pulse-dot" />}
                    {item.label}
                  </span>
                );
              }
              if (item.kind === "critical") {
                return (
                  <span
                    className={`osm-pbadge osm-pbadge--critical osm-pbadge--${platformBadgeVariant(item.severity)}`}
                    title={item.title}
                  >
                    {item.label}
                  </span>
                );
              }
              return (
                <span
                  className={`osm-pbadge osm-pbadge--secondary ${item.kind === "secondary" ? "osm-pbadge--status-secondary" : ""} osm-pbadge--${platformBadgeVariant(item.severity)}`}
                  title={item.title}
                >
                  {item.label}
                </span>
              );
            }}
          />
        </header>

        <div className="osm-body">

        {/* ── Progress ────────────────────────────────────────── */}
        <div className="osm-progress-section">
          <div className="osm-progress-track">
            <div
              className={`osm-progress-bar ${isActive ? "osm-progress--active" : ""} ${stage === "completed" ? "osm-progress--done" : ""} ${isDegraded ? "osm-progress--degraded" : ""} ${stage === "failed" ? "osm-progress--error" : ""}`}
              style={{ width: `${computedProgress}%`, "--bar-color": progressColor(computedProgress, stage) }}
            />
          </div>
          <div className="osm-progress-meta">
            <span className="osm-progress-pct">{computedProgress}%</span>
            <span className="osm-progress-stages">
              {t("command:ops.progressStages", { done: doneCount, total: stages.length })}
            </span>
          </div>
        </div>

        {/* ── Running Degraded Banner ────────────────────────── */}
        {isRunningDegraded && !isStalled && (
          <div className="osm-degraded-banner">
            <AlertTriangle size={14} />
            <span>
              {t("command:ops.runningDegradedMessage", {
                count: failedCount,
                defaultValue: `${failedCount} stage(s) failed — pipeline continuing in degraded mode.`,
              })}
            </span>
          </div>
        )}

        {/* ── Completed Degraded Banner ────────────────────────── */}
        {isDegraded && failedCount > 0 && (
          <div className="osm-degraded-banner">
            <AlertTriangle size={14} />
            <span>
              {t("command:ops.degradedMessage", {
                count: failedCount,
                defaultValue: `Pipeline completed with ${failedCount} stage(s) degraded. Partial data is available.`,
              })}
            </span>
          </div>
        )}

        {isSlowFinalizing && !isStalled && (
          <div className="osm-degraded-banner" style={{ borderColor: "rgba(59, 130, 246, 0.35)" }}>
            <Activity size={14} />
            <span>
              {isBusyWithoutHeartbeat
                ? t("command:ops.busyWithoutHeartbeatBanner", {
                    defaultValue: "Worker alive — processing heavy batches. Awaiting next heartbeat.",
                  })
                : hb?.stage_detail
                ? hb.stage_detail
                : t("command:ops.finalizingBanner", {
                    defaultValue: "Pipeline is finalizing large correlation batches — worker is still active.",
                  })}
            </span>
          </div>
        )}

        {/* ── Stalled / Timeout Banner ──────────────────────── */}
        {isStalled && (
          <div className="osm-stalled-banner">
            <AlertTriangle size={14} />
            <div className="osm-stalled-copy">
              <span>
                {status.stall_diagnosis?.failure_reason
                  || (stage === "timeout"
                    ? t("command:ops.timeoutMessage", { defaultValue: "Pipeline exceeded maximum duration. Partial data may be available." })
                    : t("command:ops.stalledMessage", {
                        defaultValue: "Pipeline sem heartbeat por período prolongado. O worker não está ativo.",
                      }))}
              </span>
              {status.heartbeat_age_s > 0 && (
                <small className="osm-stalled-meta">
                  {t("command:ops.stallMeta", {
                    age: status.heartbeat_age_s,
                    defaultValue: "Último heartbeat há {{age}}s — worker_alive=false",
                  })}
                </small>
              )}
            </div>
            <div className="osm-stalled-actions">
              {onRetrySync && (
                <button type="button" className="osm-reset-btn osm-reset-btn--primary" onClick={onRetrySync}>
                  {t("command:ops.retrySyncBtn", { defaultValue: "Nova execução" })}
                </button>
              )}
              {onReset && (
                <button type="button" className="osm-reset-btn" onClick={onReset}>
                  {t("command:ops.resetBtn", { defaultValue: "Resetar" })}
                </button>
              )}
            </div>
          </div>
        )}

        <PipelineIntegrityStrip integrity={integrity} kpis={kpis} stageResults={stageResults} t={t} />

        {!showIntegrityStrip && corpusSummary && (
          <p className="osm-corpus-summary">{corpusSummary}</p>
        )}

        {reconciled && (
          <div className="osm-degraded-banner" style={{ borderColor: "rgba(34, 197, 94, 0.35)" }}>
            <CheckCircle size={14} />
            <span>
              {t("command:ops.reconciledBanner", {
                defaultValue: "Operational status reconciled with live KPIs — stale degraded messages removed.",
              })}
            </span>
          </div>
        )}

        {/* ── Crawl Intelligence ──────────────────────────────── */}
        {ct && <GovernorBadge telemetry={ct} t={t} />}
        {ct && <CrawlIntel telemetry={ct} />}

        {/* ── Pipeline Stages ─────────────────────────────────── */}
        <div className="osm-pipeline">
          {stages.map((s) => {
            const state = stageState(s.key, stage, completedStages, failedStages, stages, stageResults, kpis, integrity);
            const Icon = s.icon;
            const throughput = state === "done"
              ? formatStageThroughput(s.key, stageResults[s.key], authoritative, t)
              : "";
            const stageBlob = stageResults[s.key];
            const enrichmentOnly = isOptionalEnrichmentWarning(s.key, stageBlob);
            const degradedHint = stageDegradedHint(s.key, stageBlob, kpis, integrity, t);
            const stageValidation = activeStageValidation(s.key, failedStages, stageResults, kpis, integrity);
            const warningHint = enrichmentOnly
              ? t("command:ops.linkage.fusion_enrichment_warning", {
                  defaultValue: "Enriquecimento de aviação parcial",
                })
              : "";
            return (
              <div className={`osm-stage osm-stage--${state}`} key={s.key}>
                <div className="osm-stage-dot"><StageIcon state={state} /></div>
                <div className="osm-stage-icon"><Icon size={11} /></div>
                <div className="osm-stage-info">
                  <span className="osm-stage-label">{t(`command:ops.stages.${s.key}`, { defaultValue: t(`command:ops.${s.descKey}`) })}</span>
                  {throughput && <span className="osm-stage-throughput">{throughput}</span>}
                  {degradedHint && (
                    <span
                      className={`osm-stage-degraded-hint ${
                        stageValidation === "reconciled"
                          ? "osm-stage-degraded-hint--reconciled"
                          : enrichmentOnly
                            ? "osm-stage-degraded-hint--warning"
                            : ""
                      }`}
                    >
                      {degradedHint}
                    </span>
                  )}
                  {warningHint && !degradedHint?.includes(warningHint) && (
                    <span className="osm-stage-warning-hint">{warningHint}</span>
                  )}
                </div>
                {stageValidation === "reconciled" && (
                  <span className="osm-stage-reconciled">{t("command:ops.integrity.reconciled")}</span>
                )}
                {state === "active" && (
                  <span className="osm-stage-live">{t("command:ops.liveStage")}</span>
                )}
              </div>
            );
          })}
        </div>

        {/* ── Event stream ────────────────────────────────────── */}
        {runEvents.length > 0 && (
          <div className="osm-events">
            <div className="osm-events-head">
              <Radio size={10} />
              <span>{t("command:ops.events")}</span>
              <span className="osm-events-count">{runEvents.length}</span>
            </div>
            <div className="osm-events-scroll">
              {runEvents.slice(-12).map((ev, i) => {
                const translated = translateEvent(ev.message, t);
                return (
                  <div className="osm-ev" key={i}>
                    {eventIcon(ev.message)}
                    <time className="osm-ev-time">{normalizeEventTime(ev.time)}</time>
                    <span className="osm-ev-msg">{translated.text}</span>
                    {translated.duration && <span className="osm-ev-dur">{translated.duration}</span>}
                  </div>
                );
              })}
              <div ref={eventsEndRef} />
            </div>
          </div>
        )}

        {/* ── Recent operations ───────────────────────────────── */}
        {history.length > 0 && !isActive && (
          <section className="osm-history-panel">
            <h4 className="osm-section-label">{t("command:ops.history")}</h4>
            <div className="osm-history-table" role="table">
              <div className="osm-history-thead" role="row">
                <span role="columnheader">{t("command:ops.historyCol.status", { defaultValue: "Status" })}</span>
                <span role="columnheader">{t("command:ops.historyCol.duration", { defaultValue: "Duração" })}</span>
                <span role="columnheader">{t("command:ops.historyCol.processing", { defaultValue: "Processamento" })}</span>
                <span role="columnheader">{t("command:ops.historyCol.origin", { defaultValue: "Origem" })}</span>
              </div>
              {history.slice(0, 5).map((run) => (
                <div className="osm-history-tr" role="row" key={run.operation_id}>
                  <span role="cell">
                    <span className={`osm-hist-badge osm-hist--${run.status}`}>
                      {t(`command:ops.historyStatus.${run.status}`, { defaultValue: run.status })}
                    </span>
                  </span>
                  <span className="osm-history-mono" role="cell">
                    {run.duration_ms ? `${(run.duration_ms / 1000).toFixed(1)}s` : "—"}
                  </span>
                  <span role="cell">
                    {t("command:ops.historyReviews", {
                      count: (run.reviews_processed || 0).toLocaleString("pt-BR"),
                    })}
                  </span>
                  <span className="osm-history-origin" role="cell">{run.triggered_by || "—"}</span>
                </div>
              ))}
            </div>
          </section>
        )}
        </div>
      </div>
    </div>
  );
}

function OperationalSyncModalWithBoundary(props) {
  const { t } = useTranslation(["command"]);
  return (
    <ReconciliationErrorBoundary
      fallbackLabel={t("command:ops.modalFallback", {
        defaultValue: "Operational sync panel unavailable — retry or refresh pipeline status.",
      })}
    >
      <OperationalSyncModalInner {...props} />
    </ReconciliationErrorBoundary>
  );
}

export const OperationalSyncModal = memo(OperationalSyncModalWithBoundary);
