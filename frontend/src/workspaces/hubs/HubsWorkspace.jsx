import React from "react";
import { useTranslation } from "react-i18next";
import { useAviation } from "../../hooks/useAviation";
import { useOperations } from "../../hooks/useOperations";
import { WorkspaceShell } from "../../layouts/WorkspaceShell";
import { HubOverviewStrip } from "./HubOverviewStrip";
import { HubOperationalPanel } from "./HubOperationalPanel";
import { HubRiskMatrixPanel } from "./HubRiskMatrixPanel";
import { HubIncidentsPanel } from "./HubIncidentsPanel";
import { HubGlobalNetworkPanel } from "./HubGlobalNetworkPanel";
import { HubConcentrationPanel } from "./HubConcentrationPanel";
import { HubExecutiveInsights } from "./HubExecutiveInsights";

export default function HubsWorkspace() {
  const { t } = useTranslation("hubs");
  const {
    hubDashboard,
    hubRankings,
    hubRisk,
    hubAlliances,
    hubIncidents,
    hubConcentration,
    loading,
  } = useAviation();
  const { triggerAviationSync, status: opsStatus, loading: opsLoading } = useOperations();

  const isSyncing = opsStatus.running && opsStatus.pipeline_type === "aviation";
  const classified = hubDashboard?.classified_hubs ?? 0;
  const total = hubDashboard?.airports_monitored ?? 0;
  const subtitle =
    total > 0
      ? t("pageSubtitleClassified", { classified, total })
      : t("pageSubtitle");

  return (
    <WorkspaceShell
      id="hubs"
      accent="signal"
      className="workspace-hubs"
      title={t("pageTitle")}
      subtitle={subtitle}
    >
      <div className="forecasting-grid hubs-grid">
        <section className="fg-cell fg-span-12">
          <HubOverviewStrip dashboard={hubDashboard} loading={loading} />
        </section>

        <section className="fg-cell fg-span-12">
          <HubOperationalPanel
            rankings={hubRankings}
            concentration={hubConcentration}
            loading={loading}
            onSync={triggerAviationSync}
            syncing={opsLoading || isSyncing}
          />
        </section>

        <section className="fg-cell fg-span-6">
          <HubRiskMatrixPanel hubRisk={hubRisk} loading={loading} />
        </section>

        <section className="fg-cell fg-span-6">
          <HubIncidentsPanel incidents={hubIncidents} loading={loading} />
        </section>

        <section className="fg-cell fg-span-12">
          <HubGlobalNetworkPanel hubAlliances={hubAlliances} loading={loading} />
        </section>

        <section className="fg-cell fg-span-12">
          <HubConcentrationPanel
            concentration={hubConcentration}
            rankings={hubRankings}
            loading={loading}
          />
        </section>

        <section className="fg-cell fg-span-12">
          <HubExecutiveInsights
            rankings={hubRankings}
            concentration={hubConcentration}
            dashboard={hubDashboard}
            loading={loading}
          />
        </section>
      </div>
    </WorkspaceShell>
  );
}
