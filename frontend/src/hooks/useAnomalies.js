import { useCallback, useEffect, useState } from "react";
import { fetchJson } from "../lib/apiClient";

export function useAnomalies() {
  const [anomalies, setAnomalies] = useState([]);
  const [alerts, setAlerts] = useState([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    const [anomRes, alertRes] = await Promise.allSettled([
      fetchJson("/anomalies?limit=30", []),
      fetchJson("/anomalies/alerts?limit=12", [])
    ]);
    setAnomalies(Array.isArray(anomRes.value) ? anomRes.value : []);
    setAlerts(Array.isArray(alertRes.value) ? alertRes.value : []);
    setLoading(false);
  }, []);

  useEffect(() => { load(); }, [load]);

  return { anomalies, alerts, loading, reload: load };
}
