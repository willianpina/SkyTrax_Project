import React, { memo, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { TrendingDown, TrendingUp, Minus, ChevronDown, ChevronUp } from "lucide-react";
import { OperationalModuleCard } from "../../components/forecasting/OperationalModuleCard";
import { formatScore } from "../../utils/formatMetric";

function MiniSparkline({ values }) {
  if (!values || values.length < 2) return <span className="acm-spark-empty">—</span>;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;
  const w = 52;
  const h = 16;
  const pts = values.map((v, i) => {
    const x = (i / (values.length - 1)) * w;
    const y = h - ((v - min) / range) * (h - 3) - 1.5;
    return `${x},${y}`;
  });
  const trend = values[values.length - 1] >= values[0];
  const stroke = trend ? "var(--positive)" : "var(--risk)";

  return (
    <svg width={w} height={h} className="acm-spark" viewBox={`0 0 ${w} ${h}`} aria-hidden>
      <polyline points={pts.join(" ")} fill="none" stroke={stroke} strokeWidth="1.25" strokeLinejoin="round" />
    </svg>
  );
}

function ScoreBar({ value, max }) {
  const pct = max > 0 ? (value / max) * 100 : 0;
  const cls = value >= 70 ? "acm-bar--good" : value >= 50 ? "acm-bar--mid" : "acm-bar--low";
  return (
    <div className="acm-score-cell acm-score-cell--compact">
      <span className={`acm-score-val ${cls}`}>{formatScore(value, { allowZero: true })}</span>
      <div className="acm-score-track" aria-hidden>
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
  const label =
    trend === "declining"
      ? t("command:matrix.declining", { defaultValue: "Declining" })
      : trend === "improving"
        ? t("command:matrix.improving", { defaultValue: "Improving" })
        : t("command:matrix.stableLabel", { defaultValue: "Stable" });
  return (
    <span className={`acm-trend acm-trend--${cls}`}>
      <Icon size={11} strokeWidth={2} aria-hidden />
      {label}
    </span>
  );
}

function ComplaintCell({ ratio }) {
  if (!ratio) return <span className="acm-muted">—</span>;
  const cls = ratio > 50 ? "acm-comp--high" : ratio > 30 ? "acm-comp--mid" : "acm-comp--low";
  return <span className={`acm-comp ${cls}`}>{Math.round(ratio)}%</span>;
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

function BenchmarkRuntimeTableInner({ reputation, benchmarking }) {
  const { t } = useTranslation(["benchmarking", "command"]);
  const [sortKey, setSortKey] = useState("score");
  const [sortAsc, setSortAsc] = useState(false);

  const rows = useMemo(() => {
    return (reputation || []).map((r) => {
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
      };
    });
  }, [reputation, benchmarking]);

  const sorted = useMemo(() => {
    const arr = [...rows];
    arr.sort((a, b) => {
      let va;
      let vb;
      switch (sortKey) {
        case "airline":
          va = a.airline;
          vb = b.airline;
          break;
        case "complaint":
          va = a.complaint;
          vb = b.complaint;
          break;
        case "risk":
          va = RISK_ORDER[a.risk] || 0;
          vb = RISK_ORDER[b.risk] || 0;
          break;
        default:
          va = a.score;
          vb = b.score;
      }
      if (va < vb) return sortAsc ? -1 : 1;
      if (va > vb) return sortAsc ? 1 : -1;
      return 0;
    });
    return arr;
  }, [rows, sortKey, sortAsc]);

  const maxScore = Math.max(...rows.map((r) => r.score), 1);

  const handleSort = (key) => {
    if (sortKey === key) setSortAsc(!sortAsc);
    else {
      setSortKey(key);
      setSortAsc(key === "airline");
    }
  };

  const SortIcon = ({ col }) => {
    if (sortKey !== col) return null;
    return sortAsc ? (
      <ChevronUp size={10} className="acm-sort-icon" />
    ) : (
      <ChevronDown size={10} className="acm-sort-icon" />
    );
  };

  return (
    <OperationalModuleCard
      className="benchmark-runtime-module"
      title={t("runtime.title", { defaultValue: "Benchmark runtime table" })}
      subtitle={t("runtime.subtitle", { defaultValue: "Peer reputation comparison — scrollable operational view" })}
      meta={<span className="op-module-count">{sorted.length} airlines</span>}
      status={
        <span className="op-status-pill op-status-pill--muted">
          {t("runtime.hint", { defaultValue: "Sticky header · internal scroll" })}
        </span>
      }
      bodyClassName="benchmark-runtime-module__body"
    >
      <div className="benchmark-runtime-scroll">
        <table className="acm-table acm-table--runtime">
          <thead>
            <tr>
              <th className="acm-th acm-th--airline" onClick={() => handleSort("airline")}>
                {t("command:matrix.airline")} <SortIcon col="airline" />
              </th>
              <th className="acm-th acm-th--spark">Trend</th>
              <th className="acm-th acm-th--score" onClick={() => handleSort("score")}>
                {t("command:matrix.reputation")} <SortIcon col="score" />
              </th>
              <th className="acm-th acm-th--trend">Direction</th>
              <th className="acm-th acm-th--comp" onClick={() => handleSort("complaint")}>
                {t("command:matrix.complaints")} <SortIcon col="complaint" />
              </th>
              <th className="acm-th acm-th--risk" onClick={() => handleSort("risk")}>
                {t("command:matrix.risk")} <SortIcon col="risk" />
              </th>
            </tr>
          </thead>
          <tbody>
            {sorted.map((row, i) => (
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
                  <ComplaintCell ratio={row.complaint} />
                </td>
                <td className="acm-cell acm-cell--risk">
                  <RiskBadge risk={row.risk} label={riskLabel(row.risk, t)} />
                </td>
              </tr>
            ))}
            {sorted.length === 0 && (
              <tr>
                <td colSpan={6} className="acm-empty">
                  {t("runtime.empty", { defaultValue: "No benchmark data in current window." })}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </OperationalModuleCard>
  );
}

export const BenchmarkRuntimeTable = memo(BenchmarkRuntimeTableInner);
