import React, { useMemo, useState } from "react";
import { useSharedAnalytics } from "../../hooks/AnalyticsProvider";
import { WorkspaceShell } from "../../layouts/WorkspaceShell";
import { AnomalyTimeline } from "../../components/AnomalyPanel";
import { AnomalyKpiStrip } from "./AnomalyKpiStrip";
import { AnomalyFilterBar } from "./AnomalyFilterBar";
import { AnomalySignalStream } from "./AnomalySignalStream";
import { AnomalyIncidentRuntime } from "./AnomalyIncidentRuntime";
import { AnomalyExecutiveAssessment } from "./AnomalyExecutiveAssessment";
import { useCarriersAffected, useSeverityCounts } from "./anomalyShared";

export default function AnomaliesWorkspace() {
  const { anomalies, alerts } = useSharedAnalytics();
  const [sevFilter, setSevFilter] = useState(null);

  const counts = useSeverityCounts(anomalies, alerts);
  const carriersAffected = useCarriersAffected(anomalies, alerts);
  const totalSignals = (anomalies?.length || 0) + (alerts?.length || 0);

  const filtered = useMemo(() => {
    if (!sevFilter) return anomalies || [];
    return (anomalies || []).filter((a) => a.severity === sevFilter);
  }, [anomalies, sevFilter]);

  return (
    <WorkspaceShell id="anomalies" accent="risk" className="workspace-anomalies">
      <div className="forecasting-grid anomalies-grid">
        <section className="fg-cell fg-span-12">
          <AnomalyKpiStrip counts={counts} total={totalSignals} carriersAffected={carriersAffected} />
        </section>

        <section className="fg-cell fg-span-12 anomaly-filter-wrap">
          <AnomalyFilterBar counts={counts} sevFilter={sevFilter} onFilterChange={setSevFilter} />
        </section>

        <section className="fg-cell fg-span-12">
          <article className="op-module-card anomaly-timeline-slot">
            <div className="op-module-body anomaly-timeline-module__body">
              <AnomalyTimeline anomalies={anomalies} embedded />
            </div>
          </article>
        </section>

        <section className="fg-cell fg-span-12">
          <AnomalySignalStream anomalies={anomalies} alerts={alerts} />
        </section>

        <section className="fg-cell fg-span-12">
          <AnomalyIncidentRuntime anomalies={filtered} />
        </section>

        <section className="fg-cell fg-span-12">
          <AnomalyExecutiveAssessment anomalies={anomalies} />
        </section>
      </div>
    </WorkspaceShell>
  );
}
