import { useCallback, useEffect, useState } from "react";
import { fetchJson } from "../lib/apiClient";

const EMPTY = {
  summary: {},
  quality: {},
  missing: { airlines: [], airports: [] },
  duplicates: { total: 0, details: [] },
  orphans: { airlines: 0, airports: 0, total: 0 },
  validation: { total_issues: 0, issues: [] },
  normalization: {},
  graph: { total_nodes: 0, total_edges: 0, node_types: {}, edge_types: {} },
  disruptions: { total_analyzed: 0, severity_distribution: {} },
};

export function useCoverage() {
  const [data, setData] = useState(EMPTY);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    const results = await Promise.allSettled([
      fetchJson("/aviation/coverage", {}),
      fetchJson("/aviation/coverage/quality", {}),
      fetchJson("/aviation/coverage/missing", { airlines: [], airports: [] }),
      fetchJson("/aviation/coverage/duplicates", { total: 0, details: [] }),
      fetchJson("/aviation/coverage/orphans", { airlines: 0, airports: 0, total: 0 }),
      fetchJson("/aviation/validation", { total_issues: 0, issues: [] }),
      fetchJson("/aviation/normalization", {}),
      fetchJson("/graph/stats", { total_nodes: 0, total_edges: 0, node_types: {}, edge_types: {} }),
      fetchJson("/fusion/disruptions", { total_analyzed: 0, severity_distribution: {} }),
    ]);
    setData({
      summary: results[0].value || {},
      quality: results[1].value || {},
      missing: results[2].value || { airlines: [], airports: [] },
      duplicates: results[3].value || { total: 0, details: [] },
      orphans: results[4].value || { airlines: 0, airports: 0, total: 0 },
      validation: results[5].value || { total_issues: 0, issues: [] },
      normalization: results[6].value || {},
      graph: results[7].value || EMPTY.graph,
      disruptions: results[8].value || EMPTY.disruptions,
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
