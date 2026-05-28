import React, { useMemo } from "react";
import { useTranslation } from "react-i18next";
import { useSharedAnalytics } from "../../hooks/AnalyticsProvider";
import {
  buildAirlineForecasts,
  extractTopMovers,
  computeExecutiveSummary,
  buildTemporalHeatmap,
} from "../../lib/forecastIntelligence";
import { WorkspaceShell } from "../../layouts/WorkspaceShell";
import { ExecutiveSummary } from "./ExecutiveSummary";
import { TopMovers } from "./TopMovers";
import { PredictionsTable } from "./PredictionsTable";
import { TemporalHeatmap } from "./TemporalHeatmap";
import { OperationalForecastCharts } from "./OperationalForecastCharts";

export default function ForecastingWorkspace() {
  const { t } = useTranslation(["charts", "command", "common", "nav"]);
  const { forecasts, data, snapshots, reputation } = useSharedAnalytics();

  const safeSnapshots = Array.isArray(snapshots) ? snapshots : [];
  const timeline = safeSnapshots
    .filter((s) => s?.period_end && !s.airline_id)
    .slice(0, 12)
    .map((s) => ({ month: String(s.period_end).slice(0, 10), score: s.metrics?.reputation_score || 0 }));
  const ratingTimeline = timeline.length ? timeline : data.timeline || [];

  const airlineForecasts = useMemo(
    () => buildAirlineForecasts(forecasts, reputation),
    [forecasts, reputation]
  );

  const topMovers = useMemo(() => extractTopMovers(airlineForecasts), [airlineForecasts]);
  const executiveSummary = useMemo(() => computeExecutiveSummary(airlineForecasts), [airlineForecasts]);
  const heatmapData = useMemo(() => buildTemporalHeatmap(airlineForecasts), [airlineForecasts]);

  return (
    <WorkspaceShell id="forecasting" accent="warning" className="workspace-forecasting">
      <div className="forecasting-grid">
        <section className="fg-cell fg-span-12" aria-label={t("charts:executive.stripLabel", { defaultValue: "Executive KPIs" })}>
          <ExecutiveSummary summary={executiveSummary} />
        </section>

        <section className="fg-cell fg-span-12" aria-label={t("charts:topMovers.title", { defaultValue: "Top movers" })}>
          <TopMovers movers={topMovers} />
        </section>

        <section className="fg-cell fg-span-12" aria-label={t("charts:operationalForecast.title", { defaultValue: "Operational forecast" })}>
          <OperationalForecastCharts forecasts={forecasts} ratingTimeline={ratingTimeline} />
        </section>

        <section className="fg-cell fg-span-12" aria-label={t("charts:table.title", { defaultValue: "Operational predictions" })}>
          <PredictionsTable airlines={airlineForecasts} />
        </section>

        <section className="fg-cell fg-span-12" aria-label={t("charts:heatmap.title", { defaultValue: "Risk trend matrix" })}>
          <TemporalHeatmap heatmapData={heatmapData} />
        </section>
      </div>
    </WorkspaceShell>
  );
}
