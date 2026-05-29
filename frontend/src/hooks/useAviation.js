import { useCallback, useEffect, useState } from "react";
import { fetchJson } from "../lib/apiClient";

const EMPTY = {
  airlines: [], airports: [], alliances: [], hubs: [], regions: [], premium: [],
  metadata: {},
  hubDashboard: {},
  hubRankings: [],
  hubRisk: [],
  hubAlliances: [],
  hubIncidents: [],
  hubConcentration: [],
};

const HUB_INTEL_LOADERS = [
  ["hubDashboard", "/aviation/hub-intelligence/dashboard", {}],
  ["hubRankings", "/aviation/hub-intelligence/rankings", []],
  ["hubRisk", "/aviation/hub-intelligence/risk", []],
  ["hubAlliances", "/aviation/hub-intelligence/alliances", []],
  ["hubIncidents", "/aviation/hub-intelligence/incidents", []],
  ["hubConcentration", "/aviation/hub-intelligence/concentration", []],
];

export function useAviation() {
  const [data, setData] = useState(EMPTY);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    const results = await Promise.allSettled([
      fetchJson("/aviation/airlines?limit=100", []),
      fetchJson("/aviation/airports?limit=200", []),
      fetchJson("/aviation/alliances", []),
      fetchJson("/aviation/hubs", []),
      fetchJson("/aviation/regions", []),
      fetchJson("/aviation/premium", []),
      fetchJson("/aviation/metadata", {}),
    ]);
    setData((prev) => ({
      ...prev,
      airlines: results[0].value || [],
      airports: results[1].value || [],
      alliances: results[2].value || [],
      hubs: results[3].value || [],
      regions: results[4].value || [],
      premium: results[5].value || [],
      metadata: results[6].value || {},
    }));
    setLoading(false);

    // Hub intelligence is expensive (review mention scan); load sequentially to avoid DB pool exhaustion.
    for (const [key, path, fallback] of HUB_INTEL_LOADERS) {
      const value = await fetchJson(path, fallback);
      setData((prev) => ({ ...prev, [key]: value }));
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  useEffect(() => {
    const onRefresh = () => load();
    window.addEventListener("skytrax:operational-refresh-complete", onRefresh);
    return () => window.removeEventListener("skytrax:operational-refresh-complete", onRefresh);
  }, [load]);

  return { ...data, loading, reload: load };
}
