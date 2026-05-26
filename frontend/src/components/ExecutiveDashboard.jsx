import React, { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { Activity, AlertTriangle, BarChart3, Download, Gauge, Map, RefreshCw } from "lucide-react";
import { useAnalytics } from "../hooks/useAnalytics";
import { computeExecutiveMetrics } from "../lib/executiveMetrics";
import { buildIntelligenceFeed } from "../lib/intelligenceFeed";
import {
  buildRatingOption,
  buildSentimentOption,
  buildComplaintDensityOption,
  exportReputationCsv
} from "../lib/chartConfigs";
import { AnomalyTimeline, OperationalAlertsPanel } from "./AnomalyPanel";
import { ForecastPanel } from "./ForecastPanel";
import { LanguageSwitcher } from "./LanguageSwitcher";
import { MetricCard } from "./MetricCard";
import { TopicPanel } from "./TopicPanel";
import { ChartPanel } from "./charts/ChartPanel";
import { BenchmarkingRadar } from "./charts/BenchmarkingRadar";
import { CommandRail } from "./command/CommandRail";
import { ExecutiveMetricsStrip } from "./command/ExecutiveMetricsStrip";
import { IntelligenceTimeline } from "./command/IntelligenceTimeline";
import { AnomalyFeed } from "./command/AnomalyFeed";
import { ExecutiveInsightsPanel } from "./command/ExecutiveInsightsPanel";
import { SemanticInvestigationPanel } from "./command/SemanticInvestigationPanel";
import { AirlineComparisonMatrix } from "./command/AirlineComparisonMatrix";
import { FallbackPanel } from "./ui/PanelShell";
import { FrictionMatrix } from "./FrictionMatrix";

function translateSentimentLabel(t, label) {
  const key = String(label || "").toLowerCase();
  return t(`common:sentiment.${key}`, { defaultValue: label });
}

function KpiSkeleton() {
  return (
    <section className="kpi-row">
      {[0, 1, 2, 3].map((i) => (
        <div className="tactical-metric skeleton" key={i} />
      ))}
    </section>
  );
}

export default function ExecutiveDashboard() {
  const { t, i18n } = useTranslation(["dashboard", "charts", "semantic", "benchmarking", "common", "alerts", "command"]);
  const {
    data, reputation, benchmarking, insights, snapshots, clusters,
    forecasts, anomalies, alerts, isLive, isLoading, error,
    partialErrors, reload, apiBase
  } = useAnalytics();

  const [section] = useState("executive");

  const topArs = reputation[0];
  const executiveMetrics = useMemo(
    () => computeExecutiveMetrics({ data, reputation, benchmarking, alerts, anomalies }),
    [data, reputation, benchmarking, alerts, anomalies]
  );
  const feedItems = useMemo(
    () => buildIntelligenceFeed({ anomalies, insights, forecasts, partialErrors, isLive }),
    [anomalies, insights, forecasts, partialErrors, isLive]
  );
  const sentiment = useMemo(
    () => Object.entries(data.sentiment_distribution || {}).map(([label, value]) => ({ label, value })),
    [data]
  );

  const safeSnapshots = Array.isArray(snapshots) ? snapshots : [];
  const timelineFromSnapshots = safeSnapshots
    .filter((s) => s?.period_end && !s.airline_id)
    .slice(0, 12)
    .map((s) => ({
      month: String(s.period_end).slice(0, 10),
      score: s.metrics?.reputation_score || 0,
      volume: s.metrics?.review_volume || 0
    }));

  const ratingTimeline = timelineFromSnapshots.length ? timelineFromSnapshots : data.timeline || [];
  const ratingOption = useMemo(() => buildRatingOption(ratingTimeline), [ratingTimeline]);
  const sentimentOption = useMemo(
    () => buildSentimentOption(sentiment, (label) => translateSentimentLabel(t, label)),
    [sentiment, t, i18n.language]
  );

  const complaintOption = useMemo(
    () => buildComplaintDensityOption(reputation, benchmarking.complaint_density),
    [reputation, benchmarking.complaint_density]
  );

  const statusLabel = isLive ? t("common:status.apiLive") : error || t("common:status.demoData");
  const partialSuffix = partialErrors.length ? ` · ${t("common:status.partial", { count: partialErrors.length })}` : "";
  const defaultInsight = {
    severity: "neutral",
    summary: t("dashboard:sections.noInsights"),
    airline: t("dashboard:sections.portfolio"),
    drivers: []
  };
  const signalCount = (alerts?.length || 0) + (anomalies?.filter((a) => a.severity === "high" || a.severity === "critical")?.length || 0);

  return (
    <main className="command-center">
      <CommandRail activeSection={section} signalCount={signalCount} isLive={isLive} />

      <div className="command-main">
        <header className="command-header glass-panel">
          <div>
            <p className="eyebrow">{t("dashboard:header.eyebrow")}</p>
            <h1>{t("command:title")}</h1>
            <p className="header-sub">{t("command:subtitle")}</p>
          </div>
          <div className="topbar-actions">
            <LanguageSwitcher />
            <button type="button" className="tactical-btn icon" onClick={() => exportReputationCsv(reputation, benchmarking.complaint_density)} title={t("common:actions.exportCsv")}>
              <Download size={14} />
            </button>
            <button type="button" className="tactical-btn icon" onClick={reload} title={t("common:actions.reload")}>
              <RefreshCw size={14} className={isLoading ? "spin" : ""} />
            </button>
            <span className={`ops-status ${isLive ? "live" : ""}`}>
              <span className="pulse-dot" aria-hidden />
              {statusLabel}{partialSuffix}
            </span>
          </div>
        </header>

        <ExecutiveMetricsStrip metrics={executiveMetrics} loading={isLoading} />

        {partialErrors.length > 0 && (
          <FallbackPanel title={t("command:degraded.title")} message={t("command:degraded.message")} onRetry={reload} />
        )}

        {isLoading && <KpiSkeleton />}

        <section className={`kpi-row ${isLoading ? "dimmed" : ""}`}>
          <MetricCard icon={Gauge} label={t("dashboard:kpi.ars")} value={topArs ? `${topArs.score}` : "—"} detail={topArs ? t("dashboard:kpi.arsDetailLeading", { airline: topArs.airline }) : t("dashboard:kpi.arsDetailDefault")} trend={topArs?.score > 60 ? "up" : "down"} />
          <MetricCard icon={Activity} label={t("dashboard:kpi.recommendation")} value={`${Math.round((data.recommendation_rate || 0) * 100)}%`} detail={t("dashboard:kpi.recommendationDetail")} trend="up" />
          <MetricCard icon={BarChart3} label={t("dashboard:kpi.reviewsIndexed")} value={(data.review_count || 0).toLocaleString(i18n.language === "pt" ? "pt-BR" : "en-US")} detail={t("dashboard:kpi.reviewsDetail")} />
          <MetricCard icon={AlertTriangle} label={t("dashboard:kpi.operationalAlerts")} value={alerts.length} detail={t("dashboard:kpi.operationalAlertsDetail")} tone="risk" trend={alerts.length > 3 ? "down" : "stable"} />
        </section>

        <div className="command-body">
          <div className="command-central">
            <section className="tactical-grid">
              <ForecastPanel forecasts={forecasts} />
              <ChartPanel title={t("charts:ratingEvolution.title")} subtitle={t("charts:ratingEvolution.subtitle")} option={ratingOption} accent="positive" />
            </section>
            <section className="tactical-grid">
              <AnomalyTimeline anomalies={anomalies} />
              <OperationalAlertsPanel alerts={alerts} />
            </section>
            <section className="tactical-grid">
              <ChartPanel title={t("charts:sentimentMix.title")} subtitle={t("charts:sentimentMix.subtitle")} option={sentimentOption} accent="signal" />
              <BenchmarkingRadar radarRows={benchmarking?.radar_analytics} />
            </section>
            <ExecutiveInsightsPanel insights={insights} defaultInsight={defaultInsight} />
            <AirlineComparisonMatrix reputation={reputation} benchmarking={benchmarking} />
            <section className="tactical-grid">
              <TopicPanel title={t("dashboard:topics.positiveDrivers")} rows={data.top_positive_topics || []} tone="positive" />
              <TopicPanel title={t("dashboard:topics.negativeFriction")} rows={data.top_negative_topics || []} tone="negative" />
              <ChartPanel title={t("charts:complaintDensity.title")} subtitle={t("charts:complaintDensity.subtitle")} option={complaintOption} accent="risk" />
            </section>
            <FrictionMatrix />
            <SemanticInvestigationPanel clusters={clusters} apiBase={apiBase} reputation={reputation} />
            <article className="intel-panel glass-panel map-placeholder span-full">
              <header className="intel-panel-header">
                <div className="intel-panel-titles">
                  <h2>{t("command:map.title")}</h2>
                  <span className="intel-panel-sub">{t("command:map.subtitle")}</span>
                </div>
                <Map size={16} className="muted-icon" />
              </header>
              <div className="map-layers">
                {["routes", "risk", "coverage", "alerts"].map((layer) => (
                  <span className="map-layer-chip" key={layer}>
                    <span className="map-layer-dot" aria-hidden />
                    {t(`command:map.layers.${layer}`)}
                  </span>
                ))}
              </div>
              <div className="map-grid-placeholder">
                <div className="map-scan" aria-hidden />
                <p>{t("command:map.placeholder")}</p>
              </div>
            </article>
          </div>
          <aside className="command-rail-right">
            <IntelligenceTimeline items={feedItems} />
            <AnomalyFeed anomalies={anomalies} alerts={alerts} />
          </aside>
        </div>
      </div>
    </main>
  );
}
