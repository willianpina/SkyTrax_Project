import React, { useMemo } from "react";
import { useTranslation } from "react-i18next";
import { Activity, AlertTriangle, BarChart3, Gauge } from "lucide-react";
import { useSharedAnalytics } from "../../hooks/AnalyticsProvider";
import { computeExecutiveMetrics } from "../../lib/executiveMetrics";
import { buildIntelligenceFeed } from "../../lib/intelligenceFeed";
import { buildRatingOption } from "../../lib/chartConfigs";
import { formatScore, formatPercent } from "../../utils/formatMetric";
import { WorkspaceShell } from "../../layouts/WorkspaceShell";
import { ExecutiveMetricsStrip } from "../../components/command/ExecutiveMetricsStrip";
import { MetricCard } from "../../components/MetricCard";
import { ForecastPanel } from "../../components/ForecastPanel";
import { ChartPanel } from "../../components/charts/ChartPanel";
import { OperationalAlertsPanel } from "../../components/AnomalyPanel";
import { ExecutiveInsightsPanel } from "../../components/command/ExecutiveInsightsPanel";
import { IntelligenceTimeline } from "../../components/command/IntelligenceTimeline";
import { AnomalyFeed } from "../../components/command/AnomalyFeed";
import { FallbackPanel } from "../../components/ui/PanelShell";

export default function ExecutiveWorkspace() {
  const { t, i18n } = useTranslation(["dashboard", "charts", "command", "common"]);
  const {
    data, reputation, benchmarking, insights, snapshots,
    forecasts, anomalies, alerts, isLive, isLoading, partialErrors, reload
  } = useSharedAnalytics();

  const topArs = reputation[0];
  const executiveMetrics = useMemo(
    () => computeExecutiveMetrics({ data, reputation, benchmarking, alerts, anomalies }),
    [data, reputation, benchmarking, alerts, anomalies]
  );
  const feedItems = useMemo(
    () => buildIntelligenceFeed({ anomalies, insights, forecasts, partialErrors, isLive }),
    [anomalies, insights, forecasts, partialErrors, isLive]
  );

  const safeSnapshots = Array.isArray(snapshots) ? snapshots : [];
  const timelineFromSnapshots = safeSnapshots
    .filter((s) => s?.period_end && !s.airline_id)
    .slice(0, 12)
    .map((s) => ({ month: String(s.period_end).slice(0, 10), score: s.metrics?.reputation_score || 0 }));
  const ratingTimeline = timelineFromSnapshots.length ? timelineFromSnapshots : data.timeline || [];
  const ratingOption = useMemo(() => buildRatingOption(ratingTimeline), [ratingTimeline]);

  const defaultInsight = {
    severity: "neutral",
    summary: t("dashboard:sections.noInsights"),
    airline: t("dashboard:sections.portfolio"),
    drivers: []
  };

  return (
    <WorkspaceShell id="executive" title={t("nav:nav.executive")} subtitle={t("command:subtitle")} accent="signal">
      <ExecutiveMetricsStrip metrics={executiveMetrics} loading={isLoading} />

      {partialErrors.length > 0 && (
        <FallbackPanel title={t("command:degraded.title")} message={t("command:degraded.message")} onRetry={reload} />
      )}

      <section className="kpi-row">
        <MetricCard icon={Gauge} label={t("dashboard:kpi.ars")} value={topArs ? formatScore(topArs.score, { allowZero: true }) : "—"} detail={topArs ? t("dashboard:kpi.arsDetailLeading", { airline: topArs.airline }) : t("dashboard:kpi.arsDetailDefault")} trend={topArs?.score > 60 ? "up" : "down"} />
        <MetricCard icon={Activity} label={t("dashboard:kpi.recommendation")} value={formatPercent((data.recommendation_rate || 0) * 100, { allowZero: true })} detail={t("dashboard:kpi.recommendationDetail")} trend="up" />
        <MetricCard icon={BarChart3} label={t("dashboard:kpi.reviewsIndexed")} value={(data.review_count || 0).toLocaleString(i18n.language === "pt" ? "pt-BR" : "en-US")} detail={t("dashboard:kpi.reviewsDetail")} />
        <MetricCard icon={AlertTriangle} label={t("dashboard:kpi.operationalAlerts")} value={alerts.length || "—"} detail={t("dashboard:kpi.operationalAlertsDetail")} tone="risk" trend={alerts.length > 3 ? "down" : "stable"} />
      </section>

      <div className="command-body">
        <div className="command-central">
          <section className="tactical-grid">
            <ForecastPanel forecasts={forecasts} />
            <ChartPanel title={t("charts:ratingEvolution.title")} subtitle={t("charts:ratingEvolution.subtitle")} option={ratingOption} accent="positive" />
          </section>
          <OperationalAlertsPanel alerts={alerts} />
          <ExecutiveInsightsPanel insights={insights} defaultInsight={defaultInsight} />
        </div>
        <aside className="command-rail-right">
          <IntelligenceTimeline items={feedItems} />
          <AnomalyFeed anomalies={anomalies} alerts={alerts} />
        </aside>
      </div>
    </WorkspaceShell>
  );
}
