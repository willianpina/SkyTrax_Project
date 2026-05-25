import React, { useMemo } from "react";
import { useTranslation } from "react-i18next";
import { useSharedAnalytics } from "../../hooks/AnalyticsProvider";
import { buildHeatmapOption } from "../../lib/chartConfigs";
import { WorkspaceShell } from "../../layouts/WorkspaceShell";
import { SemanticInvestigationPanel } from "../../components/command/SemanticInvestigationPanel";
import { TopicPanel } from "../../components/TopicPanel";
import { ChartPanel } from "../../components/charts/ChartPanel";

export default function SemanticWorkspace() {
  const { t } = useTranslation(["semantic", "charts", "dashboard", "nav"]);
  const { data, clusters, reputation, benchmarking, apiBase } = useSharedAnalytics();

  const heatmapAirlines = Object.keys(benchmarking?.topic_heatmap || {}).slice(0, 8);
  const heatmapTopics = Array.from(
    new Set(heatmapAirlines.flatMap((slug) => (benchmarking.topic_heatmap[slug] || []).map((r) => r.label)))
  ).slice(0, 10);
  const heatmapOption = useMemo(
    () => buildHeatmapOption(heatmapAirlines, heatmapTopics, benchmarking?.topic_heatmap || {}),
    [heatmapAirlines, heatmapTopics, benchmarking?.topic_heatmap]
  );

  return (
    <WorkspaceShell id="semantic" title={t("nav:nav.semantic")} subtitle={t("semantic:lookup.subtitle")} accent="signal">
      <SemanticInvestigationPanel clusters={clusters} apiBase={apiBase} reputation={reputation} />

      <section className="tactical-grid">
        <TopicPanel title={t("dashboard:topics.positiveDrivers")} rows={data.top_positive_topics || []} tone="positive" />
        <TopicPanel title={t("dashboard:topics.negativeFriction")} rows={data.top_negative_topics || []} tone="negative" />
      </section>

      <ChartPanel title={t("charts:topicHeatmap.title")} subtitle={t("charts:topicHeatmap.subtitle")} option={heatmapOption} height={320} accent="warning" />
    </WorkspaceShell>
  );
}
