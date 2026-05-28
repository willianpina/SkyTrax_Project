import React, { useMemo } from "react";
import { useTranslation } from "react-i18next";
import { Activity, AlertTriangle, BarChart3, Gauge } from "lucide-react";
import { useSharedAnalytics } from "../../hooks/AnalyticsProvider";
import { computeExecutiveMetrics } from "../../lib/executiveMetrics";
import { buildIntelligenceFeed } from "../../lib/intelligenceFeed";
import { formatScore, formatPercent } from "../../utils/formatMetric";
import { WorkspaceShell } from "../../layouts/WorkspaceShell";
import { ExecutiveMetricsStrip } from "../../components/command/ExecutiveMetricsStrip";
import { MetricCard } from "../../components/MetricCard";
import { OperationalForecastCharts } from "../forecasting/OperationalForecastCharts";
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

  return (
    <WorkspaceShell id="executive" accent="signal">
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

      <div className="command-body command-body--executive">
        <div className="command-central forecasting-grid">
          <section className="fg-cell fg-span-12 executive-forecast-module">
            <OperationalForecastCharts forecasts={forecasts} ratingTimeline={ratingTimeline} />
          </section>

          <section className="fg-cell fg-span-12 tactical-grid executive-runtime-row">
            <IntelligenceTimeline items={feedItems} />
            <AnomalyFeed anomalies={anomalies} alerts={alerts} />
          </section>

          <section className="fg-cell fg-span-12 executive-alerts-row">
            <OperationalAlertsPanel alerts={alerts} />
          </section>

          <section className="fg-cell fg-span-12 executive-insights-row">
            <ExecutiveInsightsPanel insights={insights} />
          </section>
        </div>
      </div>
    </WorkspaceShell>
  );
}
