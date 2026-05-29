import React, { memo, useState, useCallback } from "react";
import { useTranslation } from "react-i18next";
import { Search } from "lucide-react";
import { OperationalModuleCard } from "../../components/forecasting/OperationalModuleCard";
import { ConfidenceBadge } from "../../components/ui/PanelShell";

function InvestigationSemanticModuleInner({ clusters, apiBase, reputation, selectedAirline }) {
  const { t } = useTranslation("investigations");
  const [query, setQuery] = useState("");
  const [threshold, setThreshold] = useState(0.15);
  const [airline, setAirline] = useState(selectedAirline || "");
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);

  const topClusters = (clusters || []).slice(0, 6);
  const airlines = (reputation || []).map((r) => ({ slug: r.slug, name: r.airline }));

  const runSearch = useCallback(
    (q) => {
      const searchQuery = q ?? query;
      if (!searchQuery.trim()) return;
      setLoading(true);
      const params = new URLSearchParams({
        q: searchQuery,
        limit: "8",
        threshold: String(threshold),
      });
      const carrier = airline || selectedAirline;
      if (carrier) params.set("airline", carrier);
      fetch(`${apiBase}/semantic-search?${params}`)
        .then((r) => (r.ok ? r.json() : []))
        .then(setResults)
        .catch(() => setResults([]))
        .finally(() => setLoading(false));
    },
    [query, threshold, airline, selectedAirline, apiBase]
  );

  const handleClusterClick = useCallback(
    (clusterLabel) => {
      setQuery(clusterLabel);
      runSearch(clusterLabel);
    },
    [runSearch]
  );

  return (
    <OperationalModuleCard
      className="investigation-semantic-module"
      title={t("semanticTitle")}
      subtitle={t("semanticSubtitle")}
      expandable
      defaultExpanded={false}
      bodyClassName="investigation-semantic-module__body"
    >
      <div className="investigation-semantic-grid">
        <section>
          <h3 className="investigation-pane-title">{t("clustersPane")}</h3>
          {topClusters.length === 0 ? (
            <p className="muted-copy">{t("searchHint")}</p>
          ) : (
            <ul className="investigation-cluster-list" role="list">
              {topClusters.map((c) => (
                <li key={c.id}>
                  <button type="button" className="investigation-cluster-line" onClick={() => handleClusterClick(c.cluster_label)}>
                    <span className="investigation-cluster-name">{c.cluster_label}</span>
                    <span className="investigation-cluster-count">{t("reviews", { count: c.review_count })}</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </section>
        <section>
          <h3 className="investigation-pane-title">{t("searchPane")}</h3>
          <div className="investigation-search-row">
            <input
              className="investigation-search-input"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder={t("searchPlaceholder")}
              onKeyDown={(e) => e.key === "Enter" && runSearch()}
            />
            <button type="button" className="investigation-search-btn" onClick={() => runSearch()} disabled={loading || !query.trim()}>
              <Search size={14} />
            </button>
          </div>
          <div className="investigation-search-filters">
            <label className="investigation-filter-range">
              {t("threshold")}
              <input type="range" min="0.05" max="0.5" step="0.05" value={threshold} onChange={(e) => setThreshold(Number(e.target.value))} />
              <span>{Math.round(threshold * 100)}%</span>
            </label>
            <select className="investigation-filter-select" value={airline} onChange={(e) => setAirline(e.target.value)}>
              <option value="">{t("allAirlines")}</option>
              {airlines.map((a) => (
                <option key={a.slug} value={a.slug}>{a.name}</option>
              ))}
            </select>
          </div>
          <div className="investigation-search-results">
            {loading ? (
              <div className="investigation-module-skeleton" />
            ) : results.length === 0 ? (
              <p className="muted-copy">{query ? t("noResults") : t("searchHint")}</p>
            ) : (
              <ul className="investigation-result-list" role="list">
                {results.map((row) => (
                  <li className="investigation-result-line" key={row.review_id}>
                    <div className="investigation-result-head">
                      <strong>{row.airline}</strong>
                      <ConfidenceBadge score={Math.round((row.score || 0) * 100)} label={t("relevance")} />
                    </div>
                    <p>{row.title || row.text?.slice(0, 160)}</p>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </section>
      </div>
    </OperationalModuleCard>
  );
}

export const InvestigationSemanticModule = memo(InvestigationSemanticModuleInner);
