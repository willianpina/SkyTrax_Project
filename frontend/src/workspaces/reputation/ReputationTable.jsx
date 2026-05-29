import React, { memo, useMemo, useState, useCallback } from "react";
import { useTranslation } from "react-i18next";
import { ChevronUp, ChevronDown, Search } from "lucide-react";
import { TrendArrow } from "../../components/ui/PanelShell";
import { OperationalBadge } from "../../components/ui/OperationalBadge";
import { formatScore } from "../../utils/formatMetric";
import { GROUP_MODES, groupRegistry } from "../../lib/reputationIntelligence";

const PAGE_SIZE = 40;

const RISK_VARIANTS = {
  critical: "danger",
  high: "danger",
  attention: "warning",
  stable: "success",
  excellent: "info",
};

function ReputationTableInner({ registry, onAirlineClick }) {
  const { t } = useTranslation(["dashboard"]);
  const [sortCol, setSortCol] = useState("score");
  const [sortDir, setSortDir] = useState("asc");
  const [search, setSearch] = useState("");
  const [groupMode, setGroupMode] = useState("global");
  const [visibleCount, setVisibleCount] = useState(PAGE_SIZE);

  const toggleSort = useCallback((col) => {
    if (sortCol === col) setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    else { setSortCol(col); setSortDir("asc"); }
  }, [sortCol]);

  const filtered = useMemo(() => {
    if (!search.trim()) return registry;
    const q = search.toLowerCase();
    return registry.filter((r) =>
      r.airline.toLowerCase().includes(q) ||
      r.country.toLowerCase().includes(q) ||
      (r.alliance || "").toLowerCase().includes(q)
    );
  }, [registry, search]);

  const sorted = useMemo(() => {
    const arr = [...filtered];
    arr.sort((a, b) => {
      let av = a[sortCol], bv = b[sortCol];
      if (typeof av === "string") av = av.toLowerCase();
      if (typeof bv === "string") bv = bv.toLowerCase();
      if (av < bv) return sortDir === "asc" ? -1 : 1;
      if (av > bv) return sortDir === "asc" ? 1 : -1;
      return 0;
    });
    return arr;
  }, [filtered, sortCol, sortDir]);

  const groups = useMemo(() => groupRegistry(sorted, groupMode), [sorted, groupMode]);

  const SortIcon = ({ col }) => {
    if (sortCol !== col) return null;
    return sortDir === "asc" ? <ChevronUp size={11} /> : <ChevronDown size={11} />;
  };

  const columns = [
    { key: "rank", label: t("dashboard:reputation.table.rank"), width: "3rem" },
    { key: "airline", label: t("dashboard:reputation.table.airline"), width: "auto" },
    { key: "country", label: t("dashboard:reputation.table.country"), width: "7rem" },
    { key: "alliance", label: t("dashboard:reputation.table.alliance"), width: "7rem" },
    { key: "score", label: t("dashboard:reputation.table.score"), width: "4.5rem" },
    { key: "reviewCount", label: t("dashboard:reputation.table.reviews"), width: "5rem" },
    { key: "trend", label: t("dashboard:reputation.table.trend"), width: "4rem" },
    { key: "complaints", label: t("dashboard:reputation.table.complaints"), width: "5.5rem" },
    { key: "operationalRisk", label: t("dashboard:reputation.table.risk"), width: "5rem" },
    { key: "stability", label: t("dashboard:reputation.table.stability"), width: "5rem" },
    { key: "incidents", label: t("dashboard:reputation.table.incidents"), width: "5rem" },
  ];

  return (
    <div className="rep-table-container">
      <div className="rep-table-toolbar">
        <div className="rep-table-groups">
          {GROUP_MODES.map((mode) => (
            <button
              key={mode}
              type="button"
              className={`rep-group-btn ${groupMode === mode ? "rep-group-btn--active" : ""}`}
              onClick={() => setGroupMode(mode)}
            >{t(`dashboard:reputation.groups.${mode}`)}</button>
          ))}
        </div>
        <div className="rep-table-search">
          <Search size={13} />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder={t("dashboard:reputation.table.search")}
          />
        </div>
      </div>

      {groups.map((group) => (
        <div key={group.key} className="rep-table-group">
          {groupMode !== "global" && (
            <div className="rep-table-group-header">
              <span className="rep-group-label">
                {group.key === "independent"
                  ? t("dashboard:reputation.independent")
                  : t(`dashboard:reputation.regions.${group.key}`, { defaultValue: group.key })
                }
              </span>
              <span className="rep-group-count">{group.items.length}</span>
            </div>
          )}
          <table className="rep-table">
            <thead>
              <tr>
                {columns.map((col) => (
                  <th
                    key={col.key}
                    style={{ width: col.width }}
                    className={`rep-th ${sortCol === col.key ? "rep-th--active" : ""}`}
                    onClick={() => toggleSort(col.key)}
                  >
                    <span>{col.label}</span>
                    <SortIcon col={col.key} />
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {group.items.slice(0, visibleCount).map((row, idx) => (
                <tr
                  key={row.slug}
                  className={`rep-row rep-row--${row.risk} ${idx % 2 === 1 ? "rep-row--alt" : ""}`}
                  onClick={() => onAirlineClick?.(row)}
                >
                  <td className="rep-cell rep-cell--rank">{idx + 1}</td>
                  <td className="rep-cell rep-cell--airline">
                    <strong>{row.airline}</strong>
                    {row.iataCode && <span className="rep-iata-tag">{row.iataCode}</span>}
                  </td>
                  <td className="rep-cell rep-cell--country">{row.country}</td>
                  <td className="rep-cell rep-cell--alliance">
                    {row.alliance ? (
                      <span className="rep-alliance-chip">{row.alliance}</span>
                    ) : <span className="rep-muted">{t("dashboard:reputation.independent")}</span>}
                  </td>
                  <td className="rep-cell rep-cell--score">
                    <span className={`rep-score rep-score--${row.risk}`}>
                      {formatScore(row.score, { allowZero: true })}
                    </span>
                  </td>
                  <td className="rep-cell rep-cell--num metric-num">{row.reviewCount.toLocaleString("pt-BR")}</td>
                  <td className="rep-cell rep-cell--trend">
                    <TrendArrow direction={row.trend === "declining" ? "down" : row.trend === "improving" ? "up" : "stable"} />
                  </td>
                  <td className="rep-cell rep-cell--num metric-num">{formatScore(row.complaints, { allowZero: true })}</td>
                  <td className="rep-cell rep-cell--num metric-num">{row.operationalRisk || "—"}</td>
                  <td className="rep-cell rep-cell--num metric-num">{row.stability}%</td>
                  <td className="rep-cell rep-cell--incidents">
                    {row.incidents > 0 ? (
                      <OperationalBadge variant={row.incidents >= 3 ? "danger" : "warning"} compact>
                        {row.incidents}
                      </OperationalBadge>
                    ) : <span className="rep-muted">—</span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {group.items.length > visibleCount && (
            <button
              type="button"
              className="rep-show-more"
              onClick={() => setVisibleCount((v) => v + PAGE_SIZE)}
            >{t("dashboard:reputation.table.showMore", { count: group.items.length - visibleCount })}</button>
          )}
          {group.items.length === 0 && (
            <div className="rep-table-empty">{t("dashboard:reputation.table.noResults")}</div>
          )}
        </div>
      ))}
    </div>
  );
}

export const ReputationTable = memo(ReputationTableInner);
