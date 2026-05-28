import React, { memo, useMemo } from "react";
import { useTranslation } from "react-i18next";
import { buildReputationForecastOption } from "../lib/chartConfigs";
import { forecastConfidence } from "../lib/executiveMetrics";
import { formatScore, formatDeltaNumeric } from "../utils/formatMetric";
import { LazyEChart } from "./ui/LazyEChart";
import { ConfidenceBadge, PanelShell } from "./ui/PanelShell";
import { OpsAnalyticsKpis, OpsChartLegend } from "./charts/OpsAnalyticsChrome";

function ForecastChartBody({
  forecasts,
  chartHeight = 220,
  showConfidenceBadge = true,
  paneTitle,
  paneSubtitle,
}) {
  const { t, i18n } = useTranslation(["charts", "common", "command"]);
  const arsRows = (forecasts?.metrics?.reputation_score || []).filter((r) => r.horizon === "weekly");
  const primary = arsRows[0];
  const conf = forecastConfidence(primary);
  const hasForecast = arsRows.length > 0 && !conf.insufficient;

  const actualLabel = t("charts:reputationForecast.actual");
  const forecastLabel = t("charts:reputationForecast.forecast");

  const option = useMemo(
    () =>
      hasForecast
        ? buildReputationForecastOption(
            primary,
            { actualLabel, forecastLabel, insufficient: conf.insufficient },
            i18n.language
          )
        : null,
    [primary, actualLabel, forecastLabel, conf.insufficient, hasForecast, i18n.language]
  );

  const sentimentRow = (forecasts?.metrics?.sentiment || []).find((r) => r.horizon === "weekly");
  const currentArs = formatScore(primary?.current_value);
  const forecastArs = formatScore(primary?.forecast_value);
  const arsDelta = formatDeltaNumeric(
    primary?.forecast_value != null && primary?.current_value != null
      ? primary.forecast_value - primary.current_value
      : null
  );
  const trendKey = primary?.trend_direction?.toLowerCase();
  const trendLabel = trendKey
    ? t(`common:trend.${trendKey}`, { defaultValue: primary?.trend_direction })
    : primary?.trend_direction;

  const kpis = hasForecast
    ? [
        {
          label: t("charts:reputationForecast.kpiCurrent", { defaultValue: "Current ARS" }),
          value: currentArs,
          accent: "signal",
        },
        {
          label: t("charts:reputationForecast.kpiForecast", { defaultValue: "Forecast" }),
          value: forecastArs,
          sub: arsDelta !== "—" ? `Δ ${arsDelta}` : null,
          accent: "warning",
        },
        ...(sentimentRow
          ? [
              {
                label: t("charts:metrics.sentiment", { defaultValue: "Sentiment" }),
                value: `${formatScore(sentimentRow.current_value)} → ${formatScore(sentimentRow.forecast_value)}`,
                sub: trendLabel
                  ? `${sentimentRow.trend_direction === "up" || sentimentRow.trend_direction === "improving" ? "↑" : sentimentRow.trend_direction === "down" || sentimentRow.trend_direction === "declining" ? "↓" : "→"} ${trendLabel}`
                  : null,
                accent: "positive",
              },
            ]
          : []),
      ]
    : [
        {
          label: t("charts:reputationForecast.kpiPipeline", { defaultValue: "Pipeline" }),
          value: t("charts:reputationForecast.pipelineActive", { defaultValue: "Active" }),
          accent: "signal",
        },
        {
          label: t("charts:reputationForecast.kpiConfidence", { defaultValue: "Confidence" }),
          value: t("charts:reputationForecast.warmingUp", { defaultValue: "Warming up" }),
          accent: "warning",
        },
      ];

  const badges = showConfidenceBadge ? (
    <ConfidenceBadge
      score={conf.score}
      insufficient={conf.insufficient}
      label={
        conf.insufficient
          ? t("charts:reputationForecast.warmingUp", { defaultValue: "Confidence warming up" })
          : t("command:forecast.confidence", { score: conf.score })
      }
    />
  ) : null;

  return (
    <div className="op-chart-pane">
      {(paneTitle || paneSubtitle || badges) && (
        <header className="op-chart-pane-header">
          <div className="op-chart-pane-titles">
            {paneTitle ? <h3 className="op-module-pane-title">{paneTitle}</h3> : null}
            {paneSubtitle ? <p className="op-module-pane-sub">{paneSubtitle}</p> : null}
          </div>
          {badges ? <div className="op-chart-pane-meta">{badges}</div> : null}
        </header>
      )}

      <OpsAnalyticsKpis items={kpis} />

      <div className="ops-chart-stage">
        {!hasForecast ? (
          <p className="muted-copy ops-empty-state">{t("charts:reputationForecast.empty")}</p>
        ) : (
          <LazyEChart option={option} height={chartHeight} className="ops-chart-canvas" />
        )}
      </div>

      {hasForecast ? (
        <OpsChartLegend
          items={[
            { label: actualLabel, tone: "positive" },
            { label: forecastLabel, tone: "warning" },
          ]}
        />
      ) : null}
    </div>
  );
}

function ForecastPanelInner({
  forecasts,
  className = "",
  chartHeight = 220,
  embedded = false,
}) {
  const { t } = useTranslation(["charts", "command"]);

  if (embedded) {
    return (
      <ForecastChartBody
        forecasts={forecasts}
        chartHeight={chartHeight}
        showConfidenceBadge={false}
        paneTitle={t("charts:reputationForecast.title")}
        paneSubtitle={t("charts:reputationForecast.subtitle")}
      />
    );
  }

  const arsRows = (forecasts?.metrics?.reputation_score || []).filter((r) => r.horizon === "weekly");
  const primary = arsRows[0];
  const conf = forecastConfidence(primary);

  const badges = (
    <ConfidenceBadge
      score={conf.score}
      insufficient={conf.insufficient}
      label={
        conf.insufficient
          ? t("charts:reputationForecast.warmingUp", { defaultValue: "Confidence warming up" })
          : t("command:forecast.confidence", { score: conf.score })
      }
    />
  );

  return (
    <PanelShell
      title={t("charts:reputationForecast.title")}
      subtitle={t("charts:reputationForecast.subtitle")}
      badges={badges}
      accent="warning"
      expandable
      defaultExpanded
      className={`ops-analytics-panel forecast-panel ${className}`.trim()}
    >
      <ForecastChartBody forecasts={forecasts} chartHeight={chartHeight} showConfidenceBadge={false} />
    </PanelShell>
  );
}

export const ForecastPanel = memo(ForecastPanelInner);
