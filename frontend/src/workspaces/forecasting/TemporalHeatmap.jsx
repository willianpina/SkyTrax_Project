import React, { memo, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { TrendingDown, TrendingUp, Minus, ChevronDown, ChevronUp } from "lucide-react";
import { formatDeltaNumeric } from "../../utils/formatMetric";

const RISK_ORDER = { critical: 4, high: 3, medium: 2, low: 1 };

function riskFromDelta(d) {
  const a = Math.abs(d);
  if (a >= 6) return "critical";
  if (a >= 4) return "high";
  if (a >= 2) return "medium";
  return "low";
}

function Sparkline({ values }) {
  if (!values.length) return <span className="trm-spark-empty">—</span>;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;
  const w = 64;
  const h = 20;
  const pts = values.map((v, i) => {
    const x = (i / Math.max(values.length - 1, 1)) * w;
    const y = h - ((v - min) / range) * (h - 4) - 2;
    return `${x},${y}`;
  });
  const last = values[values.length - 1];
  const first = values[0];
  const stroke = last >= first ? "var(--accent-positive, #34c48a)" : "var(--accent-risk, #ef4444)";

  return (
    <svg width={w} height={h} className="trm-spark" viewBox={`0 0 ${w} ${h}`}>
      <polyline points={pts.join(" ")} fill="none" stroke={stroke} strokeWidth="1.5" strokeLinejoin="round" />
    </svg>
  );
}

function DeltaCell({ value }) {
  const cls = value > 0 ? "trm-delta--pos" : value < 0 ? "trm-delta--neg" : "trm-delta--flat";
  return (
    <span className={`trm-delta ${cls}`}>
      {formatDeltaNumeric(value, { threshold: 0 })}
    </span>
  );
}

function StatusBadge({ risk }) {
  return <span className={`trm-badge trm-badge--${risk}`}>{risk}</span>;
}

function TrendIcon({ d7, d30, d90 }) {
  const avg = (d7 + d30 + d90) / 3;
  if (avg < -1.5) return <TrendingDown size={13} className="trm-trend-icon trm-trend-icon--neg" />;
  if (avg > 1.5) return <TrendingUp size={13} className="trm-trend-icon trm-trend-icon--pos" />;
  return <Minus size={13} className="trm-trend-icon trm-trend-icon--flat" />;
}

function TrendLabel({ d7, d30, d90, t }) {
  const avg = (d7 + d30 + d90) / 3;
  if (avg < -1.5) return <span className="trm-trend-lbl trm-trend-lbl--neg">{t("charts:heatmap.deterioration")}</span>;
  if (avg > 1.5) return <span className="trm-trend-lbl trm-trend-lbl--pos">{t("charts:heatmap.recovery")}</span>;
  return <span className="trm-trend-lbl trm-trend-lbl--flat">{t("charts:heatmap.stable")}</span>;
}

const SORT_KEYS = ["airline", "d7", "d30", "d90", "projected", "risk"];

function TemporalHeatmapInner({ heatmapData }) {
  const { t } = useTranslation(["charts"]);
  const [sortKey, setSortKey] = useState("risk");
  const [sortAsc, setSortAsc] = useState(false);
  const [expanded, setExpanded] = useState(false);

  const sorted = useMemo(() => {
    if (!heatmapData.length) return [];
    const rows = [...heatmapData].map((r) => ({
      ...r,
      risk: riskFromDelta(Math.min(r.d7, r.d30, r.d90, r.projected)),
    }));
    rows.sort((a, b) => {
      let va, vb;
      if (sortKey === "airline") { va = a.airline; vb = b.airline; }
      else if (sortKey === "risk") { va = RISK_ORDER[a.risk] || 0; vb = RISK_ORDER[b.risk] || 0; }
      else { va = a[sortKey] ?? 0; vb = b[sortKey] ?? 0; }
      if (va < vb) return sortAsc ? -1 : 1;
      if (va > vb) return sortAsc ? 1 : -1;
      return 0;
    });
    return rows;
  }, [heatmapData, sortKey, sortAsc]);

  const visible = expanded ? sorted : sorted.slice(0, 12);

  if (!heatmapData.length) return null;

  const handleSort = (key) => {
    if (sortKey === key) setSortAsc(!sortAsc);
    else { setSortKey(key); setSortAsc(key === "airline"); }
  };

  const SortIcon = ({ col }) => {
    if (sortKey !== col) return null;
    return sortAsc
      ? <ChevronUp size={10} className="trm-sort-icon" />
      : <ChevronDown size={10} className="trm-sort-icon" />;
  };

  return (
    <div className="op-module-card trm-section">
      <header className="op-module-header trm-head">
        <div className="op-module-header-titles">
          <h2 className="op-module-title">{t("charts:heatmap.title")}</h2>
          <p className="op-module-subtitle">{t("charts:heatmap.subtitle")}</p>
        </div>
        <span className="op-module-count trm-count">
          {sorted.length} {t("charts:predictions.airlines", { defaultValue: "airlines" })}
        </span>
      </header>

      <div className="trm-table-wrap">
        <table className="trm-table">
          <thead>
            <tr>
              <th className="trm-th trm-th--airline" onClick={() => handleSort("airline")}>
                {t("charts:predictions.airline", { defaultValue: "Airline" })} <SortIcon col="airline" />
              </th>
              <th className="trm-th trm-th--spark">Trend</th>
              <th className="trm-th trm-th--delta" onClick={() => handleSort("d7")}>
                {t("charts:heatmap.d7")} <SortIcon col="d7" />
              </th>
              <th className="trm-th trm-th--delta" onClick={() => handleSort("d30")}>
                {t("charts:heatmap.d30")} <SortIcon col="d30" />
              </th>
              <th className="trm-th trm-th--delta" onClick={() => handleSort("d90")}>
                {t("charts:heatmap.d90")} <SortIcon col="d90" />
              </th>
              <th className="trm-th trm-th--delta" onClick={() => handleSort("projected")}>
                {t("charts:heatmap.projected")} <SortIcon col="projected" />
              </th>
              <th className="trm-th trm-th--trend">Direction</th>
              <th className="trm-th trm-th--status" onClick={() => handleSort("risk")}>
                Status <SortIcon col="risk" />
              </th>
            </tr>
          </thead>
          <tbody>
            {visible.map((row) => (
              <tr key={row.slug} className={`trm-row trm-row--${row.risk}`}>
                <td className="trm-cell trm-cell--airline">{row.airline}</td>
                <td className="trm-cell trm-cell--spark">
                  <Sparkline values={[row.d90, row.d30, row.d7, row.projected]} />
                </td>
                <td className="trm-cell trm-cell--delta"><DeltaCell value={row.d7} /></td>
                <td className="trm-cell trm-cell--delta"><DeltaCell value={row.d30} /></td>
                <td className="trm-cell trm-cell--delta"><DeltaCell value={row.d90} /></td>
                <td className="trm-cell trm-cell--delta"><DeltaCell value={row.projected} /></td>
                <td className="trm-cell trm-cell--trend">
                  <TrendIcon d7={row.d7} d30={row.d30} d90={row.d90} />
                  <TrendLabel d7={row.d7} d30={row.d30} d90={row.d90} t={t} />
                </td>
                <td className="trm-cell trm-cell--status"><StatusBadge risk={row.risk} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {sorted.length > 12 && (
        <button type="button" className="trm-expand" onClick={() => setExpanded(!expanded)}>
          {expanded
            ? t("charts:predictions.collapse", { defaultValue: "Show less" })
            : t("charts:predictions.showMore", { defaultValue: "Show all {{count}}", count: sorted.length })}
        </button>
      )}
    </div>
  );
}

export const TemporalHeatmap = memo(TemporalHeatmapInner);
