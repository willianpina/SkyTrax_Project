import { useCallback, useEffect, useState } from "react";
import { fetchJson } from "../lib/apiClient";
import { mergeClientSeed } from "../workspaces/geospatial/operationalSeed";

const EMPTY_ZONES = { type: "FeatureCollection", features: [] };

const EMPTY = {
  airports: [],
  routes: [],
  events: [],
  zones: EMPTY_ZONES,
  summary: {
    airport_count: 0,
    route_count: 0,
    event_count: 0,
    hub_count: 0,
  },
};

export function useGeospatial() {
  const [data, setData] = useState(EMPTY);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    const raw = await fetchJson("/intelligence/geospatial/overview", EMPTY);
    const next = mergeClientSeed(raw);
    setData({
      airports: next.airports,
      routes: next.routes,
      events: next.events,
      zones: next.zones?.features ? next.zones : EMPTY_ZONES,
      summary: next.summary,
    });
    setLoading(false);
  }, []);

  useEffect(() => {
    load();
    const id = setInterval(load, 30000);
    return () => clearInterval(id);
  }, [load]);

  return { ...data, loading, reload: load };
}
