import { useCallback, useEffect, useState } from "react";
import { fetchJson } from "../lib/apiClient";

export function useIntelligence() {
  const [insights, setInsights] = useState([]);
  const [snapshots, setSnapshots] = useState([]);
  const [clusters, setClusters] = useState([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    const [insRes, snapRes, clustRes] = await Promise.allSettled([
      fetchJson("/insights", []),
      fetchJson("/snapshots?snapshot_type=daily&limit=30", []),
      fetchJson("/semantic-clusters", [])
    ]);
    setInsights(Array.isArray(insRes.value) ? insRes.value : []);
    setSnapshots(Array.isArray(snapRes.value) ? snapRes.value : []);
    setClusters(Array.isArray(clustRes.value) ? clustRes.value : []);
    setLoading(false);
  }, []);

  useEffect(() => { load(); }, [load]);

  return { insights, snapshots, clusters, loading, reload: load };
}
