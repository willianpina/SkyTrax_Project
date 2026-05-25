import React, { useMemo } from "react";
import { useTranslation } from "react-i18next";
import { useSharedAnalytics } from "../../hooks/AnalyticsProvider";
import { buildHeatmapOption, buildComplaintDensityOption } from "../../lib/chartConfigs";
import { WorkspaceShell } from "../../layouts/WorkspaceShell";
import { ChartPanel } from "../../components/charts/ChartPanel";
import { BenchmarkingRadar } from "../../components/charts/BenchmarkingRadar";
import { AirlineComparisonMatrix } from "../../components/command/AirlineComparisonMatrix";
import { PanelShell, TrendArrow } from "../../components/ui/PanelShell";

export default function BenchmarkingWorkspace() {
  const { t } = useTranslation(["benchmarking", "charts", "command", "nav"]);
  const { reputation, benchmarking } = useSharedAnalytics();

  const heatmapAirlines = Object.keys(benchmarking?.topic_heatmap || {}).slice(0, 8);
  const heatmapTopics = Array.from(
    new Set(heatmapAirlines.flatMap((slug) => (benchmarking.topic_heatmap[slug] || []).map((r) => r.label)))
  ).slice(0, 10);
  const heatmapOption = useMemo(
    () => buildHeatmapOption(heatmapAirlines, heatmapTopics, benchmarking?.topic_heatmap || {}),
    [heatmapAirlines, heatmapTopics, benchmarking?.topic_heatmap]
  );
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
            <span className="peer-score">{r.score}</span>
            <TrendArrow direction={r.score > 60 ? "up" : "down"} />
          </div>
        ))}
      </section>

      <AirlineComparisonMatrix reputation={reputation} benchmarking={benchmarking} />

      <section className="tactical-grid">
        <BenchmarkingRadar radarRows={benchmarking?.radar_analytics} />
        <ChartPanel title={t("charts:topicHeatmap.title")} subtitle={t("charts:topicHeatmap.subtitle")} option={heatmapOption} height={300} accent="warning" />
      </section>

      <section className="tactical-grid">
        <ChartPanel title={t("charts:complaintDensity.title")} subtitle={t("charts:complaintDensity.subtitle")} option={complaintOption} accent="risk" />
        <PanelShell title={t("benchmarking:ranking.title", { defaultValue: "Airline ranking" })} subtitle={t("benchmarking:ranking.subtitle", { defaultValue: "Sorted by ARS" })} accent="signal">
          <div className="ranking-list tactical">
            {ranked.map((r, i) => (
              <div className="ranking-row hover-intel" key={r.slug}>
                <span className="ranking-pos">#{i + 1}</span>
                <span className="ranking-airline">{r.airline}</span>
                <div className="ranking-bar-track">
                  <div className="ranking-bar positive" style={{ width: `${r.score}%` }} />
                </div>
                <span className="ranking-score">{r.score}</span>
              </div>
            ))}
          </div>
        </PanelShell>
      </section>
    </WorkspaceShell>
  );
}
