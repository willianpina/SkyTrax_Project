import React, { useMemo } from "react";
import { useTranslation } from "react-i18next";
import { useSharedAnalytics } from "../../hooks/AnalyticsProvider";
import { computeExecutiveMetrics } from "../../lib/executiveMetrics";
import { buildRatingOption, buildSentimentOption } from "../../lib/chartConfigs";
import { formatScore } from "../../utils/formatMetric";
import { WorkspaceShell } from "../../layouts/WorkspaceShell";
import { ChartPanel } from "../../components/charts/ChartPanel";
import { ExecutiveInsightsPanel } from "../../components/command/ExecutiveInsightsPanel";
import { TopicPanel } from "../../components/TopicPanel";
import { PanelShell, SeverityBadge, TrendArrow } from "../../components/ui/PanelShell";

function translateSentimentLabel(t, label) {
  return t(`common:sentiment.${String(label || "").toLowerCase()}`, { defaultValue: label });
}

export default function ReputationWorkspace() {
  const { t, i18n } = useTranslation(["dashboard", "charts", "common", "nav"]);
  const { data, reputation, benchmarking, alerts, anomalies, snapshots } = useSharedAnalytics();

  const execMetrics = useMemo(
    () => computeExecutiveMetrics({ data, reputation, benchmarking, alerts, anomalies }),
    [data, reputation, benchmarking, alerts, anomalies]
  );
  const frustration = execMetrics.find((m) => m.id === "frustration");
  const deterioration = execMetrics.find((m) => m.id === "reputation_deterioration");
  const premium = execMetrics.find((m) => m.id === "premium_dissatisfaction");

  const sentiment = useMemo(
    () => Object.entries(data.sentiment_distribution || {}).map(([label, value]) => ({ label, value })),
    [data]
  );
  const sentimentOption = useMemo(
    () => buildSentimentOption(sentiment, (label) => translateSentimentLabel(t, label)),
    [sentiment, t, i18n.language]
  );

  const safeSnapshots = Array.isArray(snapshots) ? snapshots : [];
  const timelineFromSnapshots = safeSnapshots
    .filter((s) => s?.period_end && !s.airline_id).slice(0, 12)
    .map((s) => ({ month: String(s.period_end).slice(0, 10), score: s.metrics?.reputation_score || 0 }));
  const ratingTimeline = timelineFromSnapshots.length ? timelineFromSnapshots : data.timeline || [];
  const ratingOption = useMemo(() => buildRatingOption(ratingTimeline), [ratingTimeline]);

  const defaultInsight = { severity: "neutral", summary: t("dashboard:sections.noInsights"), airline: t("dashboard:sections.portfolio"), drivers: [] };

  return (
    <WorkspaceShell id="reputation" title={t("nav:nav.reputation")} subtitle={t("dashboard:header.eyebrow")} accent="positive">
      <section className="workspace-kpi-strip">
        {[frustration, deterioration, premium].filter(Boolean).map((m) => {
          const displayValue = typeof m.value === "number" ? formatScore(m.value, { allowZero: true }) : m.value;
          return (
            <div className={`strip-metric severity-${m.severity}`} key={m.id}>
              <span className="strip-label">{t(`command:metrics.${m.id}`, { defaultValue: m.id })}</span>
              <div className="strip-value-row">
                <span className="strip-value metric-num">{displayValue}{m.unit ? <small>{m.unit}</small> : null}</span>
                <TrendArrow direction={m.trend} />
              </div>
            </div>
          );
        })}
      </section>

      <section className="tactical-grid">
        <ChartPanel title={t("charts:ratingEvolution.title")} subtitle={t("charts:ratingEvolution.subtitle")} option={ratingOption} accent="positive" />
        <ChartPanel title={t("charts:sentimentMix.title")} subtitle={t("charts:sentimentMix.subtitle")} option={sentimentOption} accent="signal" />
      </section>

      <section className="tactical-grid">
        <TopicPanel title={t("dashboard:topics.positiveDrivers")} rows={data.top_positive_topics || []} tone="positive" />
        <TopicPanel title={t("dashboard:topics.negativeFriction")} rows={data.top_negative_topics || []} tone="negative" />
      </section>

      <PanelShell title={t("dashboard:reputation.arsTable", { defaultValue: "Reputation scores" })} subtitle={t("dashboard:reputation.byAirline", { defaultValue: "By airline" })} accent="positive">
        <div className="reputation-table tactical">
          {reputation.map((r) => (
            <div className="reputation-row hover-intel" key={r.slug}>
              <strong>{r.airline}</strong>
              <span className="reputation-score metric-num">{formatScore(r.score, { allowZero: true })}</span>
              <SeverityBadge severity={r.score > 60 ? "positive" : r.score > 40 ? "medium" : "high"} />
              <span className="reputation-reviews">{r.review_count} reviews</span>
              <TrendArrow direction={r.score > 60 ? "up" : "down"} />
            </div>
          ))}
        </div>
      </PanelShell>

      <ExecutiveInsightsPanel insights={[]} defaultInsight={defaultInsight} />
    </WorkspaceShell>
  );
}
