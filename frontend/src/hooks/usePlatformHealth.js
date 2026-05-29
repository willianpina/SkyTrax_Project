import { useCallback, useEffect, useRef, useState } from "react";
import { coordinatedFetch } from "../lib/pollingCoordinator";
import { deriveOperationalHealth } from "../lib/operationalHealthEngine";

const API_BASE = (import.meta.env.VITE_API_BASE || "http://localhost:8000/api").replace(/\/$/, "");

/**
 * Platform health — single /health/pipeline coordinator (no 4-way parallel storm).
 * @param {number} pollMs
 * @param {{ enabled?: boolean, pipelineOnly?: boolean }} options
 */
export function usePlatformHealth(pollMs = 30000, options = {}) {
  const { enabled = true, pipelineOnly = true } = options;
  const [health, setHealth] = useState({
    readiness: "unknown",
    pipeline: {},
    schema: {},
    native: {},
    runtime: {},
    integrity: {},
    loading: true,
  });
  const abortRef = useRef(null);
  const cacheRef = useRef(null);

  const refresh = useCallback(async () => {
    if (!enabled) return;

    if (abortRef.current) {
      abortRef.current.abort();
    }
    const controller = new AbortController();
    abortRef.current = controller;

    const url = `${API_BASE}/operations/health/pipeline`;
    const result = await coordinatedFetch(url, {
      key: "platform-health-pipeline",
      signal: controller.signal,
    });

    if (result.aborted || controller.signal.aborted) return;

    if (!result.ok || !result.data) {
      setHealth((prev) => ({
        ...prev,
        loading: false,
        endpointsUnavailable: result.status === 404 || result.status === 0,
        readiness: result.status === 504 ? prev.readiness : "degraded",
      }));
      return;
    }

    const pipeline = result.data;
    const next = {
      readiness: pipeline.readiness || pipeline.status || "unknown",
      pipeline: pipeline.pipeline || {},
      schema: pipeline.schema || {},
      native: pipeline.native || {},
      alembic: {
        version_length: pipeline.schema?.alembic_version_length,
        safe: pipeline.schema?.alembic_safe,
        chain_valid: pipeline.schema?.migration_chain_valid,
      },
      runtime: pipeline.runtime || {},
      integrity: pipelineOnly
        ? (pipeline.accumulated_kpis ? { authoritative_kpis: pipeline.authoritative_kpis } : {})
        : (pipeline.integrity || cacheRef.current?.integrity || {}),
      blocked_stages: pipeline.blocked_stages || [],
      degraded_history: pipeline.degraded_history || [],
      startup: pipeline.startup || {},
      orchestration: pipeline.orchestration || {},
      endpointsUnavailable: false,
      loading: false,
    };
    cacheRef.current = next;
    setHealth(next);
  }, [enabled, pipelineOnly]);

  useEffect(() => {
    if (!enabled) {
      if (abortRef.current) abortRef.current.abort();
      return undefined;
    }
    refresh();
    const id = setInterval(refresh, pollMs);
    return () => {
      clearInterval(id);
      if (abortRef.current) abortRef.current.abort();
    };
  }, [refresh, pollMs, enabled]);

  const operationalHealth = deriveOperationalHealth(health);
  const badges = [
    {
      ...operationalHealth.badge,
      key: operationalHealth.badge.key,
      title: operationalHealth.summary.title,
      tooltip: operationalHealth.badge.tooltip,
    },
    {
      key: "health_score",
      label: `Health Score · ${operationalHealth.operationalHealthScore}%`,
      severity: operationalHealth.operationalHealthScore >= 85 ? "ok" : operationalHealth.operationalHealthScore >= 65 ? "warn" : "error",
      variant: "score",
      title: "Operational health score",
      tooltip: [
        "Operational health partially evaluated across runtime domains.",
        `Score: ${operationalHealth.operationalHealthScore}/100`,
        `Runtime: ${operationalHealth.badge.label}`,
        "Includes ingestion, enrichment, AI, synchronization and correlation pipelines.",
      ].join("\n"),
    },
  ];

  return {
    health,
    integrity: health.integrity || {},
    badges,
    operationalHealth,
    refresh,
    cached: cacheRef.current,
  };
}
