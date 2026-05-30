import { useCallback, useEffect, useState } from "react";
import { fetchJson } from "../lib/apiClient";
import { logDomain } from "../lib/domainAuditLog";

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
    const catalog = await fetchJson(
      "/aviation/catalog?airline_limit=100&airport_limit=200",
      { metadata: {}, airlines: [], airports: [], alliances: [], hubs: [] },
      { domain: "AVIATION" },
    );

    const airlines = catalog.airlines || [];
    const airports = catalog.airports || [];
    const alliances = catalog.alliances || [];
    const hubs = catalog.hubs || [];
    const metadata = catalog.metadata || {};

    logDomain("AVIATION", {
      endpoint: "/aviation/catalog",
      recordsReturned: airlines.length,
      recordsRendered: airlines.length,
      extra: metadata,
    });
    logDomain("HUBS", { recordsReturned: hubs.length, recordsRendered: hubs.length });
    logDomain("ALLIANCES", { recordsReturned: alliances.length, recordsRendered: alliances.length });

    setData((prev) => ({
      ...prev,
      airlines,
      airports,
      alliances,
      hubs,
      metadata,
    }));
    setLoading(false);

    const [regions, premium] = await Promise.all([
      fetchJson("/aviation/regions", []),
      fetchJson("/aviation/premium", []),
    ]);
    setData((prev) => ({ ...prev, regions: regions || [], premium: premium || [] }));

    for (const [key, path, fallback] of HUB_INTEL_LOADERS) {
      const value = await fetchJson(path, fallback, { domain: "HUBS" });
      const count = Array.isArray(value) ? value.length : Object.keys(value || {}).length;
      logDomain("HUBS", { endpoint: path, recordsReturned: count });
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
