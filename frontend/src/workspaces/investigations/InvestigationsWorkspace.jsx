import React, { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { useSharedAnalytics } from "../../hooks/AnalyticsProvider";
import { WorkspaceShell } from "../../layouts/WorkspaceShell";
import { OperationalForecastCharts } from "../forecasting/OperationalForecastCharts";
import { InvestigationOverviewStrip } from "./InvestigationOverviewStrip";
import { InvestigationFilterBar } from "./InvestigationFilterBar";
import { InvestigationIncidentsPanel } from "./InvestigationIncidentsPanel";
import { InvestigationInsightsPanel } from "./InvestigationInsightsPanel";
import { InvestigationSemanticModule } from "./InvestigationSemanticModule";

export default function InvestigationsWorkspace() {
  const { t } = useTranslation("investigations");
  const { reputation, anomalies, forecasts, clusters, insights, snapshots, data, apiBase } =
    useSharedAnalytics();
  const [selectedAirline, setSelectedAirline] = useState("");

  const airlines = useMemo(
    () => (reputation || []).map((r) => ({ slug: r.slug, name: r.airline })),
    [reputation]
  );

  const ratingTimeline = useMemo(() => {
    const safeSnapshots = Array.isArray(snapshots) ? snapshots : [];
    const fromSnapshots = safeSnapshots
      .filter((s) => s?.period_end && !s.airline_id)
      .slice(0, 12)
      .map((s) => ({
        month: String(s.period_end).slice(0, 10),
        score: s.metrics?.reputation_score || 0,
      }));
    return fromSnapshots.length ? fromSnapshots : data?.timeline || [];
  }, [snapshots, data]);

  return (
    <WorkspaceShell
      id="investigations"
      accent="warning"
      className="workspace-investigations"
      title={t("pageTitle")}
      subtitle={t("pageSubtitle")}
    >
      <div className="forecasting-grid investigations-grid">
        <section className="fg-cell fg-span-12">
          <InvestigationOverviewStrip
            anomalies={anomalies}
            insights={insights}
            reputation={reputation}
            selectedAirline={selectedAirline}
          />
        </section>

        <section className="fg-cell fg-span-12">
          <InvestigationFilterBar
            airlines={airlines}
            selectedAirline={selectedAirline}
            onChange={setSelectedAirline}
          />
        </section>

        <section className="fg-cell fg-span-12">
          <InvestigationIncidentsPanel
            anomalies={anomalies}
            reputation={reputation}
            selectedAirline={selectedAirline}
          />
        </section>

        <section className="fg-cell fg-span-12">
          <InvestigationInsightsPanel
            insights={insights}
            reputation={reputation}
            selectedAirline={selectedAirline}
          />
        </section>

        <section className="fg-cell fg-span-12">
          <OperationalForecastCharts forecasts={forecasts} ratingTimeline={ratingTimeline} />
        </section>

        <section className="fg-cell fg-span-12">
          <InvestigationSemanticModule
            clusters={clusters}
            apiBase={apiBase}
            reputation={reputation}
            selectedAirline={selectedAirline}
          />
        </section>
      </div>
    </WorkspaceShell>
  );
}
