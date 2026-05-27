import React, { memo, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { TrendingDown, TrendingUp, Minus, ChevronDown, ChevronUp } from "lucide-react";
import { PanelShell } from "../ui/PanelShell";
import { formatScore } from "../../utils/formatMetric";

function MiniSparkline({ values }) {
  if (!values || values.length < 2) return <span className="acm-spark-empty">—</span>;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;
  const w = 56;
  const h = 18;
  const pts = values.map((v, i) => {
    const x = (i / (values.length - 1)) * w;
    const y = h - ((v - min) / range) * (h - 4) - 2;
    return `${x},${y}`;
  });
  const trend = values[values.length - 1] >= values[0];
  const stroke = trend ? "var(--accent-positive, #34c48a)" : "var(--accent-risk, #ef4444)";

  return (
    <svg width={w} height={h} className="acm-spark" viewBox={`0 0 ${w} ${h}`}>
      <polyline points={pts.join(" ")} fill="none" stroke={stroke} strokeWidth="1.5" strokeLinejoin="round" />
    </svg>
  );
}

function ScoreBar({ value, max }) {
  const pct = max > 0 ? (value / max) * 100 : 0;
  const cls = value >= 70 ? "acm-bar--good" : value >= 50 ? "acm-bar--mid" : "acm-bar--low";
  return (
    <div className="acm-score-cell">
      <span className={`acm-score-val ${cls}`}>{formatScore(value, { allowZero: true })}</span>
      <div className="acm-score-track">
        <div className={`acm-score-fill ${cls}`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

function RiskBadge({ risk, label }) {
  return <span className={`acm-risk-badge acm-risk--${risk}`}>{label}</span>;
}

function TrendCell({ trend, t }) {
  const Icon = trend === "declining" ? TrendingDown : trend === "improving" ? TrendingUp : Minus;
  const cls = trend === "declining" ? "neg" : trend === "improving" ? "pos" : "flat";
  const label = trend === "declining"
    ? t("command:matrix.declining", { defaultValue: "Declining" })
    : trend === "improving"
      ? t("command:matrix.improving", { defaultValue: "Improving" })
      : t("command:matrix.stableLabel", { defaultValue: "Stable" });
  return (
    <span className={`acm-trend acm-trend--${cls}`}>
      <Icon size={12} strokeWidth={2} />
      {label}
    </span>
  );
}

function ComplaintCell({ value, ratio }) {
  if (!value && !ratio) return <span className="acm-muted">—</span>;
  const cls = ratio > 50 ? "acm-comp--high" : ratio > 30 ? "acm-comp--mid" : "acm-comp--low";
  return (
    <span className={`acm-comp ${cls}`}>
      {Math.round(ratio)}%
    </span>
  );
}

function classifyRisk(score) {
  if (score >= 70) return "low";
  if (score >= 55) return "medium";
  if (score >= 40) return "high";
  return "critical";
}

function riskLabel(risk, t) {
  const labels = {
    critical: t("command:matrix.critical", { defaultValue: "Critical" }),
    high: t("command:matrix.highRisk", { defaultValue: "High" }),
    medium: t("command:matrix.mediumRisk", { defaultValue: "Watch" }),
    low: t("command:matrix.lowRisk", { defaultValue: "Stable" }),
  };
  return labels[risk] || risk;
}

const RISK_ORDER = { critical: 4, high: 3, medium: 2, low: 1 };

function AirlineComparisonMatrixInner({ reputation, benchmarking }) {
  const { t } = useTranslation("command");
  const [sortKey, setSortKey] = useState("score");
  const [sortAsc, setSortAsc] = useState(false);
  const [expanded, setExpanded] = useState(false);

  const rows = useMemo(() => {
    const rep = reputation || [];
    return rep.map((r) => {
      const complaint = benchmarking?.complaint_density?.[r.slug] ?? r.complaintsRatio ?? 0;
      const risk = classifyRisk(r.score);
      return {
        slug: r.slug,
        airline: r.airline,
        score: r.score,
        complaint,
        risk,
        trend: r.trend || "stable",
        historyScores: r.historyScores || [],
        operationalRisk: r.operationalRisk ?? benchmarking?.operational_risk?.[r.slug] ?? 0,
        forecastDelta: r.forecastDelta ?? 0,
      };
    });
  }, [reputation, benchmarking]);

  const sorted = useMemo(() => {
    const arr = [...rows];
    arr.sort((a, b) => {
      let va, vb;
      switch (sortKey) {
        case "airline": va = a.airline; vb = b.airline; break;
        case "score": va = a.score; vb = b.score; break;
        case "complaint": va = a.complaint; vb = b.complaint; break;
        case "risk": va = RISK_ORDER[a.risk] || 0; vb = RISK_ORDER[b.risk] || 0; break;
        case "trend": va = a.forecastDelta; vb = b.forecastDelta; break;
        default: va = a.score; vb = b.score;
      }
      if (va < vb) return sortAsc ? -1 : 1;
      if (va > vb) return sortAsc ? 1 : -1;
      return 0;
    });
    return arr;
  }, [rows, sortKey, sortAsc]);

  const visible = expanded ? sorted : sorted.slice(0, 10);
  const maxScore = Math.max(...rows.map((r) => r.score), 1);

  const handleSort = (key) => {
    if (sortKey === key) setSortAsc(!sortAsc);
    else { setSortKey(key); setSortAsc(key === "airline"); }
  };

  const SortIcon = ({ col }) => {
    if (sortKey !== col) return null;
    return sortAsc
      ? <ChevronUp size={10} className="acm-sort-icon" />
      : <ChevronDown size={10} className="acm-sort-icon" />;
  };

  return (
    <PanelShell
      title={t("matrix.title")}
      subtitle={t("matrix.subtitle")}
      accent="signal"
      className="matrix-panel span-wide"
    >
      <div className="acm-wrap">
        <table className="acm-table">
          <thead>
            <tr>
              <th className="acm-th acm-th--airline" onClick={() => handleSort("airline")}>
                {t("matrix.airline")} <SortIcon col="airline" />
              </th>
              <th className="acm-th acm-th--spark">Trend</th>
              <th className="acm-th acm-th--score" onClick={() => handleSort("score")}>
                {t("matrix.reputation")} <SortIcon col="score" />
              </th>
              <th className="acm-th acm-th--trend" onClick={() => handleSort("trend")}>
                Direction <SortIcon col="trend" />
              </th>
              <th className="acm-th acm-th--comp" onClick={() => handleSort("complaint")}>
                {t("matrix.complaints")} <SortIcon col="complaint" />
              </th>
              <th className="acm-th acm-th--risk" onClick={() => handleSort("risk")}>
                {t("matrix.risk")} <SortIcon col="risk" />
              </th>
            </tr>
          </thead>
          <tbody>
            {visible.map((row, i) => (
              <tr key={row.slug} className={`acm-row acm-row--${row.risk}`}>
                <td className="acm-cell acm-cell--airline">
                  <span className="acm-rank">{i + 1}</span>
                  <span className="acm-name">{row.airline}</span>
                </td>
                <td className="acm-cell acm-cell--spark">
                  <MiniSparkline values={row.historyScores} />
                </td>
                <td className="acm-cell acm-cell--score">
                  <ScoreBar value={row.score} max={maxScore} />
                </td>
                <td className="acm-cell acm-cell--trend">
                  <TrendCell trend={row.trend} t={t} />
                </td>
                <td className="acm-cell acm-cell--comp">
                  <ComplaintCell value={row.complaint} ratio={row.complaint} />
                </td>
                <td className="acm-cell acm-cell--risk">
                  <RiskBadge risk={row.risk} label={riskLabel(row.risk, t)} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {sorted.length > 10 && (
        <button type="button" className="acm-expand" onClick={() => setExpanded(!expanded)}>
          {expanded ? t("matrix.showLess", { defaultValue: "Show less" }) : t("matrix.showMore", { defaultValue: "Show all {{count}}", count: sorted.length })}
        </button>
      )}
    </PanelShell>
  );
}

export const AirlineComparisonMatrix = memo(AirlineComparisonMatrixInner);
