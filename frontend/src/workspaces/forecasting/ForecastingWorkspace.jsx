import React, { useMemo } from "react";
import { useTranslation } from "react-i18next";
import { useSharedAnalytics } from "../../hooks/AnalyticsProvider";
import { buildRatingOption } from "../../lib/chartConfigs";
import {
  buildAirlineForecasts,
  extractTopMovers,
  computeExecutiveSummary,
  buildTemporalHeatmap
} from "../../lib/forecastIntelligence";
import { WorkspaceShell } from "../../layouts/WorkspaceShell";
import { ForecastPanel } from "../../components/ForecastPanel";
import { ChartPanel } from "../../components/charts/ChartPanel";
import { ExecutiveSummary } from "./ExecutiveSummary";
import { TopMovers } from "./TopMovers";
import { PredictionsTable } from "./PredictionsTable";
import { TemporalHeatmap } from "./TemporalHeatmap";

export default function ForecastingWorkspace() {
  const { t } = useTranslation(["charts", "command", "common", "nav"]);
  const { forecasts, data, snapshots, reputation } = useSharedAnalytics();

  const safeSnapshots = Array.isArray(snapshots) ? snapshots : [];
  const timeline = safeSnapshots
    .filter((s) => s?.period_end && !s.airline_id)
    .slice(0, 12)
    .map((s) => ({ month: String(s.period_end).slice(0, 10), score: s.metrics?.reputation_score || 0 }));
  const ratingTimeline = timeline.length ? timeline : data.timeline || [];
  const ratingOption = useMemo(() => buildRatingOption(ratingTimeline), [ratingTimeline]);

  const airlineForecasts = useMemo(
    () => buildAirlineForecasts(forecasts, reputation),
    [forecasts, reputation]
  );

  const topMovers = useMemo(() => extractTopMovers(airlineForecasts), [airlineForecasts]);
  const executiveSummary = useMemo(() => computeExecutiveSummary(airlineForecasts), [airlineForecasts]);
  const heatmapData = useMemo(() => buildTemporalHeatmap(airlineForecasts), [airlineForecasts]);

  return (
    <WorkspaceShell
      id="forecasting"
      title={t("nav:nav.forecasting")}
      subtitle={t("charts:reputationForecast.subtitle")}
      accent="warning"
    >
      <ExecutiveSummary summary={executiveSummary} />

      <TopMovers movers={topMovers} />

      <ForecastPanel forecasts={forecasts} />

      <ChartPanel
        title={t("charts:ratingEvolution.title")}
        subtitle={t("charts:ratingEvolution.subtitle")}
        option={ratingOption}
        accent="positive"
      />

      <PredictionsTable airlines={airlineForecasts} />

      <TemporalHeatmap heatmapData={heatmapData} />
    </WorkspaceShell>
  );
}
