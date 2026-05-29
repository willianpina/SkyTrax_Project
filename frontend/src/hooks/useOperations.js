import { useCallback, useEffect, useRef, useState } from "react";
import { fetchJson, API_BASE } from "../lib/apiClient";
import { coordinatedFetch, getPollingBackoffMs } from "../lib/pollingCoordinator";
import { brasiliaTime } from "../utils/datetime";

const POLL_INTERVAL_MS = 3000;
const GRACE_POLLS = 4;
const STALE_SOFT_S = 120;
const STALE_DEFAULT_HARD_S = 240;
const STALE_FINAL_HARD_S = 480;
const MAX_POLL_DURATION_MS = 5 * 60 * 60 * 1000;

const STATUS_URL = `${API_BASE}/operations/status`;
const STATUS_KEY = "ops-status-poll";

const TERMINAL_STAGES = new Set(["idle", "completed", "completed_degraded", "failed"]);
const FINAL_STAGES = new Set(["fusion", "snapshots"]);
const SLOW_OK_STATUSES = new Set([
  "running",
  "running_degraded",
  "running_slow",
  "busy_without_heartbeat",
  "finalizing",
  "persisting",
]);

function lastActivityIso(s) {
  return s.last_heartbeat_at || s.heartbeat?.last_heartbeat_at || s.updated_at;
}

function staleHardThreshold(s) {
  const stage = s.stage || "";
  const ps = s.pipeline_status || "";
  if (FINAL_STAGES.has(stage) || ps === "finalizing" || ps === "persisting") {
    return STALE_FINAL_HARD_S;
  }
  return STALE_DEFAULT_HARD_S;
}

function detectStaleness(s) {
  if (!s.running) return s;

  const activityAt = lastActivityIso(s);
  if (!activityAt) return s;

  try {
    const activityDate = new Date(activityAt);
    if (isNaN(activityDate.getTime())) return s;
    const ageS = (Date.now() - activityDate.getTime()) / 1000;
    const next = { ...s, stale_seconds: Math.round(ageS) };

    if (ageS <= STALE_SOFT_S) return next;

    const hard = staleHardThreshold(s);
    const ps = s.pipeline_status || "";

    if (s.busy_without_heartbeat) {
      return {
        ...next,
        stale_warning: true,
        busy_without_heartbeat: true,
        worker_alive: true,
        pipeline_status: "busy_without_heartbeat",
      };
    }

    if (typeof s.worker_alive === "boolean" && !s.worker_alive) {
      return {
        ...next,
        running: false,
        stage: "stalled",
        pipeline_status: "stalled",
        worker_alive: false,
        stale: true,
      };
    }

    if (ageS <= hard || SLOW_OK_STATUSES.has(ps)) {
      if (ageS > STALE_SOFT_S && !TERMINAL_STAGES.has(s.stage)) {
        return {
          ...next,
          stale_warning: true,
          worker_alive: s.worker_alive === true,
          pipeline_status: SLOW_OK_STATUSES.has(ps) ? ps : "running_slow",
        };
      }
      return next;
    }

    if (!s.stale) {
      return {
        ...next,
        stale: true,
        running: false,
        stage: "stalled",
        pipeline_status: "stalled",
        worker_alive: false,
      };
    }
    return next;
  } catch {
    return s;
  }
}

const IDLE_STATUS = {
  running: false,
  stage: "idle",
  progress: 0,
  events: [],
  active_layers: [],
  pipeline_type: "full",
};

const DOMAINS_REFRESH_EVENT = "skytrax:operational-refresh-complete";

function notifyDomainsRefresh() {
  if (typeof window !== "undefined") {
    window.dispatchEvent(new CustomEvent(DOMAINS_REFRESH_EVENT));
  }
}

export function useOperations({ pollingEnabled = true } = {}) {
  const [status, setStatus] = useState(IDLE_STATUS);
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(false);
  const pollTimerRef = useRef(null);
  const pollAbortRef = useRef(null);
  const activeOperationRef = useRef("");
  const graceRef = useRef(0);
  const pollStartRef = useRef(null);
  const pollingActiveRef = useRef(false);

  const fetchHistory = useCallback(async () => {
    const h = await fetchJson("/operations/history?limit=10", []);
    setHistory(h);
  }, []);

  const stopPolling = useCallback(() => {
    pollingActiveRef.current = false;
    if (pollTimerRef.current) {
      clearTimeout(pollTimerRef.current);
      pollTimerRef.current = null;
    }
    if (pollAbortRef.current) {
      pollAbortRef.current.abort();
      pollAbortRef.current = null;
    }
    graceRef.current = 0;
    pollStartRef.current = null;
  }, []);

  const pollOnce = useCallback(async () => {
    if (!pollingActiveRef.current) return;

    if (pollStartRef.current && Date.now() - pollStartRef.current > MAX_POLL_DURATION_MS) {
      setStatus((prev) => ({
        ...prev,
        running: false,
        stage: "timeout",
        stale: true,
        events: [
          ...(prev.events || []),
          { time: brasiliaTime(), message: "Pipeline polling timed out — maximum duration exceeded" },
        ],
      }));
      stopPolling();
      fetchHistory();
      return;
    }

    if (pollAbortRef.current) {
      pollAbortRef.current.abort();
    }
    const controller = new AbortController();
    pollAbortRef.current = controller;

    const result = await coordinatedFetch(STATUS_URL, {
      key: STATUS_KEY,
      signal: controller.signal,
    });

    if (result.aborted || !pollingActiveRef.current) return;

    const s = result.data || IDLE_STATUS;
    s.events = s.events || [];
    s.active_layers = s.active_layers || [];
    s.pipeline_type = s.pipeline_type || "full";

    const checked = detectStaleness(s);
    const expectedOp = activeOperationRef.current;
    if (
      expectedOp &&
      checked.operation_id &&
      checked.operation_id !== expectedOp &&
      !TERMINAL_STAGES.has(checked.stage)
    ) {
      scheduleNext();
      return;
    }

    if (checked.stale || checked.stage === "stalled") {
      setStatus(checked);
      stopPolling();
      fetchHistory();
      return;
    }

    if (checked.running || (checked.stage && !TERMINAL_STAGES.has(checked.stage))) {
      graceRef.current = 0;
      if (checked.operation_id) activeOperationRef.current = checked.operation_id;
      setStatus(checked);
    } else {
      if (!checked.running && TERMINAL_STAGES.has(checked.stage)) {
        activeOperationRef.current = "";
      }
      graceRef.current += 1;
      if (graceRef.current >= GRACE_POLLS) {
        setStatus(checked);
        stopPolling();
        fetchHistory();
        if (TERMINAL_STAGES.has(checked.stage)) {
          notifyDomainsRefresh();
        }
        return;
      }
    }

    scheduleNext();

    function scheduleNext() {
      if (!pollingActiveRef.current) return;
      const backoff = getPollingBackoffMs(STATUS_URL);
      const delay = Math.max(POLL_INTERVAL_MS, backoff);
      pollTimerRef.current = setTimeout(pollOnce, delay);
    }
  }, [stopPolling, fetchHistory]);

  const startPolling = useCallback(() => {
    if (pollingActiveRef.current) return;
    pollingActiveRef.current = true;
    graceRef.current = 0;
    pollStartRef.current = Date.now();
    pollOnce();
  }, [pollOnce]);

  const triggerRefresh = useCallback(async ({ force = false } = {}) => {
    setLoading(true);
    try {
      const url = force
        ? `${API_BASE}/operations/refresh?force=true`
        : `${API_BASE}/operations/refresh`;
      const resp = await fetch(url, { method: "POST" });
      const data = await resp.json();

      if (resp.status === 409 && data.status === "already_running") {
        setStatus((prev) => ({
          ...prev,
          running: true,
          operation_id: data.operation_id || prev.operation_id,
          stage: data.lifecycle_state || data.stage || "running",
        }));
        activeOperationRef.current = data.operation_id || "";
        startPolling();
        return data;
      }

      if (!resp.ok && resp.status !== 202) {
        const detail = data.detail || data.status || "dispatch_failed";
        setStatus((prev) => ({
          ...prev,
          running: false,
          stage: "idle",
          events: [
            ...(prev.events || []),
            { time: brasiliaTime(), message: `Pipeline dispatch failed: ${detail}` },
          ],
        }));
        return { status: "error", detail };
      }

      const accepted = data.status === "accepted" || data.queued === true;
      const opId = data.operation_id || "";
      setStatus({
        running: true,
        stage: data.lifecycle_state || "queued",
        progress: 2,
        operation_id: opId,
        active_layers: ["discovery", "crawl", "metadata", "semantic", "knowledge_graph", "forecasting", "anomalies", "insights", "fusion", "snapshots"],
        pipeline_type: "full",
        events: [{
          time: brasiliaTime(),
          message: accepted ? `Pipeline agendada (op: ${opId})` : "Pipeline triggered",
        }],
      });
      activeOperationRef.current = opId;
      startPolling();
      return data;
    } catch (err) {
      console.error("triggerRefresh failed", err);
      return { status: "error" };
    } finally {
      setLoading(false);
    }
  }, [startPolling]);

  const triggerAviationSync = useCallback(async () => {
    setLoading(true);
    try {
      const resp = await fetch(`${API_BASE}/operations/refresh/aviation`, { method: "POST" });
      const data = await resp.json();

      if (resp.status === 409 && data.status === "already_running") {
        activeOperationRef.current = data.operation_id || "";
        startPolling();
        return data;
      }

      if (!resp.ok && resp.status !== 202) {
        return { status: "error", detail: data.detail };
      }

      const opId = data.operation_id || "";
      setStatus({
        running: true,
        stage: data.lifecycle_state || "queued",
        progress: 2,
        operation_id: opId,
        active_layers: ["aviation_master", "airport_discovery", "aviation_metadata", "hub_intelligence"],
        pipeline_type: "aviation",
        events: [{ time: brasiliaTime(), message: `Aviation sync agendada (op: ${opId})` }],
      });
      activeOperationRef.current = opId;
      startPolling();
      return data;
    } catch (err) {
      console.error("triggerAviationSync failed", err);
      return { status: "error" };
    } finally {
      setLoading(false);
    }
  }, [startPolling]);

  const resetPipeline = useCallback(async () => {
    try {
      await fetch(`${API_BASE}/operations/reset`, { method: "POST" });
      setStatus({ ...IDLE_STATUS });
      activeOperationRef.current = "";
      stopPolling();
      fetchHistory();
    } catch (err) {
      console.error("resetPipeline failed", err);
    }
  }, [stopPolling, fetchHistory]);

  useEffect(() => {
    if (!pollingEnabled) {
      stopPolling();
      return undefined;
    }

    let cancelled = false;
    (async () => {
      const s = await fetchJson("/operations/status", IDLE_STATUS);
      if (cancelled) return;
      s.events = s.events || [];
      s.active_layers = s.active_layers || [];
      s.pipeline_type = s.pipeline_type || "full";
      const checked = detectStaleness(s);
      setStatus(checked);
      activeOperationRef.current = checked.running ? (checked.operation_id || "") : "";
      if (checked.running && !checked.stale) startPolling();
    })();
    fetchHistory();
    return () => {
      cancelled = true;
      stopPolling();
    };
  }, [pollingEnabled, startPolling, stopPolling, fetchHistory]);

  return {
    status,
    history,
    loading,
    triggerRefresh,
    triggerAviationSync,
    resetPipeline,
    fetchHistory,
    startPolling,
    stopPolling,
  };
}
