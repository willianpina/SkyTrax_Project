import { useCallback, useEffect, useState } from "react";
import { fetchJson } from "../lib/apiClient";

const EMPTY = { airlines: [], airports: [], alliances: [], hubs: [], regions: [], premium: [], metadata: {} };

export function useAviation() {
  const [data, setData] = useState(EMPTY);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    const [airlines, airports, alliances, hubs, regions, premium, metadata] = await Promise.allSettled([
      fetchJson("/aviation/airlines?limit=100", []),
      fetchJson("/aviation/airports?limit=100", []),
      fetchJson("/aviation/alliances", []),
      fetchJson("/aviation/hubs", []),
      fetchJson("/aviation/regions", []),
      fetchJson("/aviation/premium", []),
      fetchJson("/aviation/metadata", {}),
    ]);
    setData({
      airlines: airlines.value || [],
      airports: airports.value || [],
      alliances: alliances.value || [],
      hubs: hubs.value || [],
      regions: regions.value || [],
      premium: premium.value || [],
      metadata: metadata.value || {},
    });
    setLoading(false);
  }, []);

  useEffect(() => { load(); }, [load]);

  return { ...data, loading, reload: load };
}
