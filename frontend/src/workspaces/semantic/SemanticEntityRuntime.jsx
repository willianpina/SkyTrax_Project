import React, { memo, useState, useCallback } from "react";
import { useTranslation } from "react-i18next";
import { Search } from "lucide-react";
import { OperationalModuleCard } from "../../components/forecasting/OperationalModuleCard";

function SemanticEntityRuntimeInner({ clusters, apiBase, reputation }) {
  const { t } = useTranslation("semantic");
  const [query, setQuery] = useState("");
  const [threshold, setThreshold] = useState(0.15);
  const [airline, setAirline] = useState("");
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
      if (airline) params.set("airline", airline);
      fetch(`${apiBase}/semantic-search?${params}`)
        .then((r) => (r.ok ? r.json() : []))
        .then(setResults)
        .catch(() => setResults([]))
        .finally(() => setLoading(false));
    },
    [query, threshold, airline, apiBase]
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
      className="semantic-entity-module"
      title={t("exploreTitle")}
      subtitle={t("exploreSubtitle")}
      expandable
      defaultExpanded={false}
      bodyClassName="semantic-entity-module__body"
    >
      <div className="semantic-entity-grid semantic-entity-grid--minimal">
        <section className="semantic-entity-clusters">
          <h3 className="semantic-pane-title">{t("clustersPane")}</h3>
          {topClusters.length === 0 ? (
            <p className="semantic-pane-empty muted-copy">{t("emptyDetail")}</p>
          ) : (
            <ul className="semantic-cluster-list" role="list">
              {topClusters.map((c) => (
                <li key={c.id}>
                  <button
                    type="button"
                    className="semantic-cluster-line"
                    onClick={() => handleClusterClick(c.cluster_label)}
                  >
                    <span className="semantic-cluster-name">{c.cluster_label}</span>
                    <span className="semantic-cluster-count">
                      {t("reviews", { count: c.review_count })}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="semantic-entity-search">
          <h3 className="semantic-pane-title">{t("searchPane")}</h3>
          <div className="semantic-search-row">
            <input
              className="semantic-search-input"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder={t("searchPlaceholder")}
              onKeyDown={(e) => e.key === "Enter" && runSearch()}
            />
            <button
              type="button"
              className="semantic-search-btn"
              onClick={() => runSearch()}
              disabled={loading || !query.trim()}
              aria-label={t("searchPane")}
            >
              <Search size={14} />
            </button>
          </div>
          <div className="semantic-search-filters">
            <label className="semantic-filter-range">
              {t("threshold")}
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
            <select
              className="semantic-filter-select"
              value={airline}
              onChange={(e) => setAirline(e.target.value)}
            >
              <option value="">{t("allAirlines")}</option>
              {airlines.map((a) => (
                <option key={a.slug} value={a.slug}>
                  {a.name}
                </option>
              ))}
            </select>
          </div>
          <div className="semantic-search-results">
            {loading ? (
              <div className="semantic-search-skeleton" />
            ) : results.length === 0 ? (
              <p className="semantic-search-hint muted-copy">
                {query ? t("noResults") : t("searchHint")}
              </p>
            ) : (
              <ul className="semantic-result-list semantic-result-list--minimal" role="list">
                {results.map((row) => (
                  <li className="semantic-result-line" key={row.review_id}>
                    <strong>{row.airline}</strong>
                    <p>{row.title || row.text?.slice(0, 140)}</p>
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

export const SemanticEntityRuntime = memo(SemanticEntityRuntimeInner);
