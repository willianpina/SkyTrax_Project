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
    const summary = await fetchJson("/aviation/coverage", {});
    const quality = await fetchJson("/aviation/coverage/quality", {});
    setData((prev) => ({
      ...prev,
      summary: summary || {},
      quality: quality || {},
    }));
    setLoading(false);

    const secondary = await Promise.allSettled([
      fetchJson("/aviation/coverage/missing", { airlines: [], airports: [] }),
      fetchJson("/aviation/coverage/duplicates", { total: 0, details: [] }),
      fetchJson("/aviation/coverage/orphans", { airlines: 0, airports: 0, total: 0 }),
      fetchJson("/aviation/validation", { total_issues: 0, issues: [] }),
      fetchJson("/aviation/normalization", {}),
      fetchJson("/graph/stats", { total_nodes: 0, total_edges: 0, node_types: {}, edge_types: {} }),
      fetchJson("/fusion/disruptions", { total_analyzed: 0, severity_distribution: {} }),
    ]);
    setData((prev) => ({
      ...prev,
      missing: secondary[0].value || { airlines: [], airports: [] },
      duplicates: secondary[1].value || { total: 0, details: [] },
      orphans: secondary[2].value || { airlines: 0, airports: 0, total: 0 },
      validation: secondary[3].value || { total_issues: 0, issues: [] },
      normalization: secondary[4].value || {},
      graph: secondary[5].value || EMPTY.graph,
      disruptions: secondary[6].value || EMPTY.disruptions,
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
