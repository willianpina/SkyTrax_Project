import { useCallback, useEffect, useState } from "react";
import { fetchJson, EMPTY_BENCHMARKING } from "../lib/apiClient";

export function useBenchmarking() {
  const [reputation, setReputation] = useState([]);
  const [benchmarking, setBenchmarking] = useState(EMPTY_BENCHMARKING);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    const [repRes, benchRes] = await Promise.allSettled([
      fetchJson("/reputation", []),
      fetchJson("/benchmarking", EMPTY_BENCHMARKING)
    ]);
    setReputation(Array.isArray(repRes.value) ? repRes.value : []);
    setBenchmarking(benchRes.value || EMPTY_BENCHMARKING);
    setLoading(false);
  }, []);

  useEffect(() => { load(); }, [load]);

  return { reputation, benchmarking, loading, reload: load };
}
