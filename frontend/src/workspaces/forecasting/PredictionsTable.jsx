import React, { memo, useMemo, useState, useCallback } from "react";
import { useTranslation } from "react-i18next";
import { ChevronUp, ChevronDown, Filter } from "lucide-react";
import { TrendArrow, ConfidenceBadge } from "../../components/ui/PanelShell";
import { formatScore, formatDeltaNumeric, isNoise } from "../../utils/formatMetric";

const RISK_ORDER = { critical: 4, high: 3, medium: 2, low: 1 };

function PredictionsTableInner({ airlines }) {
  const { t } = useTranslation(["charts", "common"]);
  const [sortKey, setSortKey] = useState("scoreDelta");
  const [sortDir, setSortDir] = useState("asc");
  const [riskFilter, setRiskFilter] = useState("all");
  const [showFilters, setShowFilters] = useState(false);

  const handleSort = useCallback((key) => {
    setSortDir((prev) => (sortKey === key ? (prev === "asc" ? "desc" : "asc") : "asc"));
    setSortKey(key);
  }, [sortKey]);

  const filtered = useMemo(() => {
    let result = [...airlines];
    if (riskFilter !== "all") {
      result = result.filter((a) => a.risk === riskFilter);
    }
    return result;
  }, [airlines, riskFilter]);

  const sorted = useMemo(() => {
    return [...filtered].sort((a, b) => {
      let av = a[sortKey];
      let bv = b[sortKey];
      if (sortKey === "risk") {
        av = RISK_ORDER[av] || 0;
        bv = RISK_ORDER[bv] || 0;
      }
      if (sortKey === "airline") {
        av = (av || "").toLowerCase();
        bv = (bv || "").toLowerCase();
      }
      if (av < bv) return sortDir === "asc" ? -1 : 1;
      if (av > bv) return sortDir === "asc" ? 1 : -1;
      return 0;
    });
  }, [filtered, sortKey, sortDir]);

  const SortIcon = ({ col }) => {
    if (sortKey !== col) return null;
    return sortDir === "asc" ? <ChevronUp size={11} /> : <ChevronDown size={11} />;
  };

  const columns = [
    { key: "airline", label: t("charts:table.airline", { defaultValue: "Airline" }) },
    { key: "scoreCurrent", label: t("charts:table.current", { defaultValue: "Current" }) },
    { key: "scoreForecast", label: t("charts:table.forecast", { defaultValue: "Forecast" }) },
    { key: "scoreDelta", label: "Δ" },
    { key: "trend", label: t("charts:table.trend", { defaultValue: "Trend" }) },
    { key: "risk", label: t("charts:table.risk", { defaultValue: "Risk" }) },
    { key: "confidence", label: t("charts:table.confidence", { defaultValue: "Conf." }) },
    { key: "complaints", label: t("charts:table.complaints", { defaultValue: "Complaints" }) },
    { key: "sentiment", label: t("charts:table.sentiment", { defaultValue: "Sentiment" }) }
  ];

  return (
    <div className="op-module-card predictions-table-container">
      <header className="op-module-header predictions-table-toolbar">
        <div className="op-module-header-titles">
          <h2 className="op-module-title">
            {t("charts:table.title", { defaultValue: "Operational Predictions" })}
          </h2>
          <p className="op-module-subtitle">
            {t("charts:table.subtitle", { defaultValue: "Airline-level forecast signals" })}
          </p>
        </div>
        <div className="op-module-meta">
          <button
            type="button"
            className="filter-toggle-btn"
            onClick={() => setShowFilters((s) => !s)}
            aria-expanded={showFilters}
          >
            <Filter size={13} />
            {t("charts:table.filters", { defaultValue: "Filters" })}
          </button>
        </div>
      </header>

      {showFilters && (
        <div className="predictions-filters fade-in">
          <label className="filter-item">
            <span>{t("charts:table.risk", { defaultValue: "Risk" })}</span>
            <select value={riskFilter} onChange={(e) => setRiskFilter(e.target.value)}>
              <option value="all">{t("charts:table.all", { defaultValue: "All" })}</option>
              <option value="critical">{t("common:severity.critical")}</option>
              <option value="high">{t("common:severity.high")}</option>
              <option value="medium">{t("common:severity.medium")}</option>
              <option value="low">{t("common:severity.low")}</option>
            </select>
          </label>
        </div>
      )}

      <div className="predictions-table-scroll">
        <table className="predictions-table">
          <thead>
            <tr>
              {columns.map((col) => (
                <th
                  key={col.key}
                  className={`pt-th ${sortKey === col.key ? "pt-th--active" : ""}`}
                  onClick={() => handleSort(col.key)}
                >
                  <span>{col.label}</span>
                  <SortIcon col={col.key} />
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {sorted.map((row, idx) => {
              const deltaDisplay = formatDeltaNumeric(row.scoreDelta);
              const complaintDisplay = formatScore(row.complaints, { allowZero: false });
              const complaintDeltaDisplay = formatDeltaNumeric(row.complaintDelta);
              const sentimentDisplay = formatScore(row.sentiment, { allowZero: false });
              const sentimentDeltaDisplay = formatDeltaNumeric(row.sentimentDelta);

              return (
                <tr key={row.slug} className={`pt-row ${idx % 2 === 0 ? "pt-row--even" : ""}`}>
                  <td className="pt-cell pt-cell--airline">{row.airline}</td>
                  <td className="pt-cell pt-cell--num metric-num">{formatScore(row.scoreCurrent, { allowZero: true })}</td>
                  <td className="pt-cell pt-cell--num metric-num">{formatScore(row.scoreForecast, { allowZero: true })}</td>
                  <td className={`pt-cell pt-cell--delta metric-num ${row.scoreDelta < 0 ? "delta-neg" : row.scoreDelta > 0 ? "delta-pos" : ""}`}>
                    {deltaDisplay}
                  </td>
                  <td className="pt-cell">
                    <TrendArrow direction={row.trend} />
                  </td>
                  <td className="pt-cell">
                    <span className={`ob ob--${row.risk === "critical" || row.risk === "high" ? "danger" : row.risk === "medium" ? "warning" : "success"}`}>
                      {t(`common:severity.${row.risk}`)}
                    </span>
                  </td>
                  <td className="pt-cell pt-cell--num">
                    <ConfidenceBadge score={row.confidence} insufficient={row.confidence < 30} />
                  </td>
                  <td className={`pt-cell pt-cell--num metric-num ${row.complaintDelta > 5 ? "delta-neg" : ""}`}>
                    {complaintDisplay}
                    {!isNoise(row.complaintDelta) && (
                      <small className={row.complaintDelta > 0 ? "delta-neg" : "delta-pos"}>
                        {" "}{complaintDeltaDisplay}
                      </small>
                    )}
                  </td>
                  <td className={`pt-cell pt-cell--num metric-num ${row.sentimentDelta < -3 ? "delta-neg" : row.sentimentDelta > 3 ? "delta-pos" : ""}`}>
                    {sentimentDisplay}
                    {!isNoise(row.sentimentDelta) && (
                      <small className={row.sentimentDelta < 0 ? "delta-neg" : "delta-pos"}>
                        {" "}{sentimentDeltaDisplay}
                      </small>
                    )}
                  </td>
                </tr>
              );
            })}
            {sorted.length === 0 && (
              <tr>
                <td colSpan={columns.length} className="pt-empty">
                  {t("charts:reputationForecast.empty")}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      <div className="predictions-table-footer">
        <span className="pt-count">
          {sorted.length} / {airlines.length} {t("charts:table.airlines", { defaultValue: "airlines" })}
        </span>
      </div>
    </div>
  );
}

export const PredictionsTable = memo(PredictionsTableInner);
