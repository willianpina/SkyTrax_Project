import React from "react";
import { useTranslation } from "react-i18next";
import { useAllianceIntel } from "../../hooks/useAllianceIntel";
import { WorkspaceShell } from "../../layouts/WorkspaceShell";
import { AllianceOverviewStrip } from "./AllianceOverviewStrip";
import { AlliancePanoramaPanel } from "./AlliancePanoramaPanel";
import { AllianceComparisonPanel } from "./AllianceComparisonPanel";
import { AllianceNetworkPanel } from "./AllianceNetworkPanel";
import { AllianceAnalyticsFeed } from "./AllianceAnalyticsFeed";

export default function AlliancesWorkspace() {
  const { t } = useTranslation("alliances");
  const { alliances, fusionSignals, hubAlliances, loading } = useAllianceIntel();

  return (
    <WorkspaceShell
      id="alliances"
      accent="warning"
      className="workspace-alliances"
      title={t("pageTitle")}
      subtitle={t("pageSubtitle")}
    >
      <div className="forecasting-grid alliances-grid">
        <section className="fg-cell fg-span-12">
          <AllianceOverviewStrip alliances={alliances} hubAlliances={hubAlliances} loading={loading} />
        </section>

        <section className="fg-cell fg-span-12">
          <AlliancePanoramaPanel alliances={alliances} loading={loading} />
        </section>

        <section className="fg-cell fg-span-12">
          <AllianceComparisonPanel alliances={alliances} loading={loading} />
        </section>

        <section className="fg-cell fg-span-12">
          <AllianceNetworkPanel alliances={alliances} loading={loading} />
        </section>

        <section className="fg-cell fg-span-12">
          <AllianceAnalyticsFeed
            alliances={alliances}
            fusionSignals={fusionSignals}
            loading={loading}
          />
        </section>
      </div>
    </WorkspaceShell>
  );
}
