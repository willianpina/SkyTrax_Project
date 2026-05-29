import React, { memo, useMemo } from "react";
import { useTranslation } from "react-i18next";
import { Award, BarChart3, ShieldAlert, Users } from "lucide-react";
import { OperationalModuleCard } from "../../components/forecasting/OperationalModuleCard";
import { formatScore } from "../../utils/formatMetric";
import { TrendArrow } from "../../components/ui/PanelShell";

function BenchmarkKpiStripInner({ reputation }) {
  const { t } = useTranslation(["benchmarking", "common"]);
  const ranked = useMemo(
    () => [...(reputation || [])].sort((a, b) => (b.score || 0) - (a.score || 0)),
    [reputation]
  );

  const leaders = ranked.slice(0, 3);
  const avgScore =
    ranked.length > 0 ? ranked.reduce((s, r) => s + (r.score || 0), 0) / ranked.length : 0;
  const highRisk = ranked.filter((r) => (r.score || 0) < 55).length;

  return (
    <OperationalModuleCard
      className="benchmark-kpi-module"
      title={t("kpi.title", { defaultValue: "Benchmark intelligence" })}
      subtitle={t("kpi.subtitle", { defaultValue: "Portfolio peer performance snapshot" })}
      meta={
        <span className="op-module-count">
          {ranked.length} {t("kpi.airlines", { defaultValue: "airlines" })}
        </span>
      }
      bodyClassName="benchmark-kpi-module__body"
    >
      <div className="benchmark-kpi-grid">
        {leaders.map((r, i) => (
          <div className={`benchmark-leader-card benchmark-leader-card--rank-${i + 1}`} key={r.slug}>
            <span className="benchmark-leader-rank">#{i + 1}</span>
            <strong className="benchmark-leader-name">{r.airline}</strong>
            <span className="benchmark-leader-score metric-num">
              {formatScore(r.score, { allowZero: true })}
            </span>
            <TrendArrow direction={r.score > 60 ? "up" : "down"} />
          </div>
        ))}

        <div className="benchmark-stat-card">
          <Users size={14} aria-hidden />
          <span className="benchmark-stat-label">{t("kpi.monitored", { defaultValue: "Monitored" })}</span>
          <span className="benchmark-stat-value">{ranked.length}</span>
        </div>
        <div className="benchmark-stat-card">
          <BarChart3 size={14} aria-hidden />
          <span className="benchmark-stat-label">{t("kpi.avgScore", { defaultValue: "Avg ARS" })}</span>
          <span className="benchmark-stat-value metric-num">{formatScore(avgScore, { allowZero: true })}</span>
        </div>
        <div className="benchmark-stat-card benchmark-stat-card--risk">
          <ShieldAlert size={14} aria-hidden />
          <span className="benchmark-stat-label">{t("kpi.atRisk", { defaultValue: "At risk" })}</span>
          <span className="benchmark-stat-value">{highRisk}</span>
        </div>
        <div className="benchmark-stat-card">
          <Award size={14} aria-hidden />
          <span className="benchmark-stat-label">{t("kpi.leader", { defaultValue: "Leader" })}</span>
          <span className="benchmark-stat-value benchmark-stat-value--text">
            {leaders[0]?.airline || "—"}
          </span>
        </div>
      </div>
    </OperationalModuleCard>
  );
}

export const BenchmarkKpiStrip = memo(BenchmarkKpiStripInner);
