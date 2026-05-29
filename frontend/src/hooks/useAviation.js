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
      fetchJson("/aviation/hub-intelligence/dashboard", {}),
      fetchJson("/aviation/hub-intelligence/rankings", []),
      fetchJson("/aviation/hub-intelligence/risk", []),
      fetchJson("/aviation/hub-intelligence/alliances", []),
      fetchJson("/aviation/hub-intelligence/incidents", []),
      fetchJson("/aviation/hub-intelligence/concentration", []),
    ]);
    setData({
      airlines: results[0].value || [],
      airports: results[1].value || [],
      alliances: results[2].value || [],
      hubs: results[3].value || [],
      regions: results[4].value || [],
      premium: results[5].value || [],
      metadata: results[6].value || {},
      hubDashboard: results[7].value || {},
      hubRankings: results[8].value || [],
      hubRisk: results[9].value || [],
      hubAlliances: results[10].value || [],
      hubIncidents: results[11].value || [],
      hubConcentration: results[12].value || [],
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
