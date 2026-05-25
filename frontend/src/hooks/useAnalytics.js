import { useCallback, useEffect, useState } from "react";
import { API_BASE, FALLBACK_ANALYTICS, EMPTY_BENCHMARKING, fetchJson } from "../lib/apiClient";

export function useAnalytics() {
  const [data, setData] = useState(FALLBACK_ANALYTICS);
  const [reputation, setReputation] = useState([]);
  const [benchmarking, setBenchmarking] = useState(EMPTY_BENCHMARKING);
  const [insights, setInsights] = useState([]);
  const [snapshots, setSnapshots] = useState([]);
  const [clusters, setClusters] = useState([]);
  const [forecasts, setForecasts] = useState({ metrics: {}, airlines: [], generated_at: null });
  const [anomalies, setAnomalies] = useState([]);
  const [alerts, setAlerts] = useState([]);
  const [isLive, setIsLive] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState("");
  const [partialErrors, setPartialErrors] = useState([]);

  const load = useCallback(async () => {
    setIsLoading(true);
    setPartialErrors([]);
    const results = await Promise.allSettled([
      fetchJson("/analytics", FALLBACK_ANALYTICS),
      fetchJson("/reputation", []),
      fetchJson("/benchmarking", EMPTY_BENCHMARKING),
      fetchJson("/insights", []),
      fetchJson("/snapshots?snapshot_type=daily&limit=30", []),
      fetchJson("/semantic-clusters", []),
      fetchJson("/forecasting", { metrics: {}, airlines: [] }),
      fetchJson("/anomalies?limit=30", []),
      fetchJson("/anomalies/alerts?limit=12", [])
    ]);

    const errors = [];
    const [
      analytics, reputationPayload, benchmarkingPayload,
      insightsPayload, snapshotsPayload, clustersPayload,
      forecastsPayload, anomaliesPayload, alertsPayload
    ] = results.map((result, index) => {
      if (result.status === "rejected") {
        errors.push(`request_${index}`);
        return null;
      }
      return result.value;
    });

    setData(analytics || FALLBACK_ANALYTICS);
    setReputation(Array.isArray(reputationPayload) ? reputationPayload : []);
    setBenchmarking(benchmarkingPayload || EMPTY_BENCHMARKING);
    setInsights(Array.isArray(insightsPayload) ? insightsPayload : []);
    setSnapshots(Array.isArray(snapshotsPayload) ? snapshotsPayload : []);
    setClusters(Array.isArray(clustersPayload) ? clustersPayload : []);
    setForecasts(forecastsPayload?.metrics ? forecastsPayload : { metrics: {}, airlines: [] });
    setAnomalies(Array.isArray(anomaliesPayload) ? anomaliesPayload : []);
    setAlerts(Array.isArray(alertsPayload) ? alertsPayload : []);

    const analyticsOk = results[0].status === "fulfilled" && analytics !== FALLBACK_ANALYTICS;
    setIsLive(analyticsOk || results[1].status === "fulfilled");
    setError(errors.length ? "Some API modules unavailable" : "");
    setPartialErrors(errors);
    setIsLoading(false);
  }, []);

  useEffect(() => { load(); }, [load]);

  return {
    data, reputation, benchmarking, insights, snapshots, clusters,
    forecasts, anomalies, alerts, isLive, isLoading, error,
    partialErrors, reload: load, apiBase: API_BASE
  };
}
