import React, { useMemo } from "react";
import { useTranslation } from "react-i18next";
import { useSharedAnalytics } from "../../hooks/AnalyticsProvider";
import { forecastConfidence } from "../../lib/executiveMetrics";
import { buildRatingOption } from "../../lib/chartConfigs";
import { baseChartTheme, axisStyle, PALANTIR_COLORS } from "../../lib/chartTheme";
import { WorkspaceShell } from "../../layouts/WorkspaceShell";
import { ForecastPanel } from "../../components/ForecastPanel";
import { ChartPanel } from "../../components/charts/ChartPanel";
import { PanelShell, ConfidenceBadge, TrendArrow, OperationalTag } from "../../components/ui/PanelShell";

export default function ForecastingWorkspace() {
  const { t } = useTranslation(["charts", "command", "common", "nav"]);
  const { forecasts, data, snapshots } = useSharedAnalytics();

  const allMetrics = Object.entries(forecasts?.metrics || {});

  const safeSnapshots = Array.isArray(snapshots) ? snapshots : [];
  const timeline = safeSnapshots
    .filter((s) => s?.period_end && !s.airline_id).slice(0, 12)
    .map((s) => ({ month: String(s.period_end).slice(0, 10), score: s.metrics?.reputation_score || 0 }));
  const ratingTimeline = timeline.length ? timeline : data.timeline || [];
  const ratingOption = useMemo(() => buildRatingOption(ratingTimeline), [ratingTimeline]);

  const metricSummaries = allMetrics.flatMap(([metric, rows]) =>
    (Array.isArray(rows) ? rows : []).filter((r) => r.horizon === "weekly").map((r) => ({ metric, ...r }))
  );

  return (
    <WorkspaceShell id="forecasting" title={t("nav:nav.forecasting")} subtitle={t("charts:reputationForecast.subtitle")} accent="warning">
      <ForecastPanel forecasts={forecasts} />

      <ChartPanel title={t("charts:ratingEvolution.title")} subtitle={t("charts:ratingEvolution.subtitle")} option={ratingOption} accent="positive" />

      <PanelShell
        title={t("charts:forecastMetrics.title", { defaultValue: "Forecast overview" })}
        subtitle={t("charts:forecastMetrics.subtitle", { defaultValue: "All tracked metrics" })}
        accent="warning"
        expandable
      >
        <div className="forecast-detail-grid tactical">
          {metricSummaries.map((row) => {
            const conf = forecastConfidence(row);
            return (
              <div className="forecast-detail-card hover-intel" key={`${row.metric}-${row.horizon}`}>
                <div className="chip-head">
                  <strong>{t(`charts:metrics.${row.metric}`, { defaultValue: row.metric.replace(/_/g, " ") })}</strong>
                  <ConfidenceBadge score={conf.score} insufficient={conf.insufficient} />
                </div>
                <div className="forecast-values">
                  <span>{row.current_value ?? "—"}</span>
                  <span className="forecast-arrow">→</span>
                  <span>{row.forecast_value ?? "—"}</span>
                </div>
                <div className="forecast-meta">
                  <OperationalTag>{conf.method}</OperationalTag>
                  <TrendArrow direction={row.trend_direction} />
                </div>
              </div>
            );
          })}
          {metricSummaries.length === 0 && <p className="muted-copy">{t("charts:reputationForecast.empty")}</p>}
        </div>
      </PanelShell>
    </WorkspaceShell>
  );
}
