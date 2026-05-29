import { useCallback, useEffect, useState } from "react";
import { fetchJson } from "../lib/apiClient";
import { logDomain } from "../lib/domainAuditLog";

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
    const alliances = await fetchJson("/aviation/alliances", []);
    logDomain("ALLIANCES", {
      endpoint: "/aviation/alliances",
      recordsReturned: alliances.length,
      recordsRendered: alliances.length,
    });
    setData((prev) => ({ ...prev, alliances: alliances || [] }));
    setLoading(false);

    const secondary = await Promise.allSettled([
      fetchJson("/fusion/signals?limit=50", []),
      fetchJson("/aviation/hub-intelligence/alliances", []),
    ]);
    const hubAlliances = secondary[1].value || [];
    logDomain("ALLIANCES", {
      endpoint: "/aviation/hub-intelligence/alliances",
      recordsReturned: hubAlliances.length,
    });
    setData((prev) => ({
      ...prev,
      fusionSignals: secondary[0].value || [],
      hubAlliances,
    }));
  }, []);

  useEffect(() => { load(); }, [load]);

  useEffect(() => {
    const onRefresh = () => load();
    window.addEventListener("skytrax:operational-refresh-complete", onRefresh);
    return () => window.removeEventListener("skytrax:operational-refresh-complete", onRefresh);
  }, [load]);

  return { ...data, loading, reload: load };
}
