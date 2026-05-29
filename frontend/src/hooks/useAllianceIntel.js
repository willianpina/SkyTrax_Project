import { useCallback, useEffect, useState } from "react";
import { fetchJson } from "../lib/apiClient";

const EMPTY = {
  alliances: [],
  fusionSignals: [],
  hubAlliances: [],
};

export function useAllianceIntel() {
  const [data, setData] = useState(EMPTY);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    const results = await Promise.allSettled([
      fetchJson("/aviation/alliances", []),
      fetchJson("/fusion/signals?limit=50", []),
      fetchJson("/aviation/hub-intelligence/alliances", []),
    ]);
    setData({
      alliances: results[0].value || [],
      fusionSignals: results[1].value || [],
      hubAlliances: results[2].value || [],
    });
    setLoading(false);
  }, []);

  useEffect(() => { load(); }, [load]);

  useEffect(() => {
    const onRefresh = () => load();
    window.addEventListener("skytrax:operational-refresh-complete", onRefresh);
    return () => window.removeEventListener("skytrax:operational-refresh-complete", onRefresh);
  }, [load]);

  return { ...data, loading, reload: load };
}
