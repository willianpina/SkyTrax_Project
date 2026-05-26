import React, { useMemo } from "react";
import { useTranslation } from "react-i18next";
import { useSharedAnalytics } from "../../hooks/AnalyticsProvider";
import { buildComplaintDensityOption } from "../../lib/chartConfigs";
import { formatScore } from "../../utils/formatMetric";
import { WorkspaceShell } from "../../layouts/WorkspaceShell";
import { ChartPanel } from "../../components/charts/ChartPanel";
import { BenchmarkingRadar } from "../../components/charts/BenchmarkingRadar";
import { AirlineComparisonMatrix } from "../../components/command/AirlineComparisonMatrix";
import { PanelShell, TrendArrow } from "../../components/ui/PanelShell";
import { FrictionMatrix } from "../../components/FrictionMatrix";

export default function BenchmarkingWorkspace() {
  const { t } = useTranslation(["benchmarking", "charts", "command", "nav"]);
  const { reputation, benchmarking } = useSharedAnalytics();

  const complaintOption = useMemo(
    () => buildComplaintDensityOption(reputation, benchmarking.complaint_density),
    [reputation, benchmarking.complaint_density]
  );

  const ranked = [...reputation].sort((a, b) => (b.score || 0) - (a.score || 0));
  const leaders = ranked.slice(0, 3);

  return (
    <WorkspaceShell id="benchmarking" title={t("nav:nav.benchmarking")} subtitle={t("benchmarking:subtitle", { defaultValue: "Competitive intelligence and peer comparison" })} accent="signal">
      <section className="workspace-kpi-strip">
        {leaders.map((r, i) => (
          <div className={`peer-card glass-panel rank-${i + 1}`} key={r.slug}>
            <span className="peer-rank">#{i + 1}</span>
            <strong>{r.airline}</strong>
            <span className="peer-score metric-num">{formatScore(r.score, { allowZero: true })}</span>
            <TrendArrow direction={r.score > 60 ? "up" : "down"} />
          </div>
        ))}
      </section>

      <AirlineComparisonMatrix reputation={reputation} benchmarking={benchmarking} />

      <section className="tactical-grid">
        <BenchmarkingRadar radarRows={benchmarking?.radar_analytics} />
        <ChartPanel title={t("charts:complaintDensity.title")} subtitle={t("charts:complaintDensity.subtitle")} option={complaintOption} accent="risk" />
      </section>

      <FrictionMatrix />

      <section className="tactical-grid">
        <PanelShell title={t("benchmarking:ranking.title", { defaultValue: "Airline ranking" })} subtitle={t("benchmarking:ranking.subtitle", { defaultValue: "Sorted by ARS" })} accent="signal">
          <div className="ranking-list tactical">
            {ranked.map((r, i) => (
              <div className="ranking-row hover-intel" key={r.slug}>
                <span className="ranking-pos">#{i + 1}</span>
                <span className="ranking-airline">{r.airline}</span>
                <div className="ranking-bar-track">
                  <div className="ranking-bar positive" style={{ width: `${Math.round(r.score)}%` }} />
                </div>
                <span className="ranking-score metric-num">{formatScore(r.score, { allowZero: true })}</span>
              </div>
            ))}
          </div>
        </PanelShell>
      </section>
    </WorkspaceShell>
  );
}
