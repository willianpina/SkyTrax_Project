import React, { memo, useState, useCallback } from "react";
import { useTranslation } from "react-i18next";
import { Search, SlidersHorizontal } from "lucide-react";
import { PanelShell, ConfidenceBadge } from "../ui/PanelShell";

function SemanticInvestigationPanelInner({ clusters, apiBase, reputation }) {
  const { t } = useTranslation(["semantic", "command"]);
  const [query, setQuery] = useState("");
  const [threshold, setThreshold] = useState(0.15);
  const [airline, setAirline] = useState("");
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);

  const airlines = (reputation || []).map((r) => ({ slug: r.slug, name: r.airline }));
  const topClusters = (clusters || []).slice(0, 6);

  const runSearch = useCallback((q) => {
    const searchQuery = q || query;
    if (!searchQuery.trim()) return;
    setLoading(true);
    const params = new URLSearchParams({
      q: searchQuery,
      limit: "8",
      threshold: String(threshold)
    });
    if (airline) params.set("airline", airline);
    fetch(`${apiBase}/semantic-search?${params}`)
      .then((r) => (r.ok ? r.json() : []))
      .then(setResults)
      .catch(() => setResults([]))
      .finally(() => setLoading(false));
  }, [query, threshold, airline, apiBase]);

  const handleClusterClick = useCallback((clusterLabel) => {
    setQuery(clusterLabel);
    runSearch(clusterLabel);
  }, [runSearch]);

  return (
    <PanelShell
      title={t("command:semantic.title")}
      subtitle={t("semantic:lookup.subtitle")}
      accent="signal"
      expandable
      defaultExpanded={false}
      className="semantic-panel span-full"
    >
      <div className="semantic-layout">
        <section className="semantic-clusters-col">
          <h3>{t("semantic:clusters.title")}</h3>
          <ul className="semantic-cluster-grid">
            {topClusters.map((c) => (
              <li
                className="cluster-card hover-intel"
                key={c.id}
                onClick={() => handleClusterClick(c.cluster_label)}
                role="button"
                tabIndex={0}
                onKeyDown={(e) => e.key === "Enter" && handleClusterClick(c.cluster_label)}
              >
                <strong>{c.cluster_label}</strong>
                <span style={{ fontSize: "10px", color: "var(--text-dim)" }}>
                  {t("semantic:clusters.reviews", { count: c.review_count })}
                </span>
                <p>{(c.centroid_terms || []).slice(0, 5).join(" · ")}</p>
                <ConfidenceBadge
                  score={Math.min(90, 40 + (c.review_count || 0) * 2)}
                  label={t("command:semantic.relevance")}
                />
              </li>
            ))}
            {topClusters.length === 0 && (
              <li className="muted-copy">{t("command:semantic.noResults")}</li>
            )}
          </ul>
        </section>

        <section className="semantic-search-col">
          <h3>{t("semantic:lookup.title")}</h3>
          <div className="investigation-controls">
            <div className="search-row tactical">
              <input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder={t("semantic:lookup.placeholder")}
                onKeyDown={(e) => e.key === "Enter" && runSearch()}
              />
              <button type="button" className="tactical-btn icon" onClick={() => runSearch()} disabled={loading || !query.trim()}>
                <Search size={14} />
              </button>
            </div>
            <div className="filter-row">
              <label>
                <SlidersHorizontal size={11} />
                {t("command:semantic.threshold")}
                <input
                  type="range"
                  min="0.05"
                  max="0.5"
                  step="0.05"
                  value={threshold}
                  onChange={(e) => setThreshold(Number(e.target.value))}
                />
                <span>{Math.round(threshold * 100)}%</span>
              </label>
              <select value={airline} onChange={(e) => setAirline(e.target.value)}>
                <option value="">{t("command:semantic.allAirlines")}</option>
                {airlines.map((a) => (
                  <option key={a.slug} value={a.slug}>{a.name}</option>
                ))}
              </select>
            </div>
          </div>
          <div className="search-results tactical">
            {loading ? (
              <div className="chart-skeleton tactical" style={{ height: 100 }} />
            ) : results.length === 0 ? (
              <p className="muted-copy">
                {query ? t("command:semantic.noResults") : t("command:semantic.clickToSearch")}
              </p>
            ) : (
              results.map((row) => (
                <div className="result-card hover-intel" key={row.review_id}>
                  <div className="result-head">
                    <strong>{row.airline}</strong>
                    <ConfidenceBadge score={Math.round((row.score || 0) * 100)} />
                  </div>
                  <p style={{ fontSize: "11px", color: "var(--text-muted)" }}>
                    {row.title || row.text?.slice(0, 120)}
                  </p>
                  {row.sentiment && <span className="op-tag">{row.sentiment}</span>}
                </div>
              ))
            )}
          </div>
        </section>

        <section className="semantic-drivers-col">
          <h3>{t("command:semantic.drivers")}</h3>
          <p className="muted-copy" style={{ marginBottom: "8px" }}>{t("command:semantic.driversHint")}</p>
          <ul className="driver-list">
            {topClusters.slice(0, 4).map((c) => (
              <li key={c.id}>
                <span className="driver-label">{c.cluster_label}</span>
                <div className="driver-bar">
                  <div style={{ width: `${Math.min(100, (c.review_count || 1) * 8)}%` }} />
                </div>
              </li>
            ))}
          </ul>
        </section>
      </div>
    </PanelShell>
  );
}

export const SemanticInvestigationPanel = memo(SemanticInvestigationPanelInner);
