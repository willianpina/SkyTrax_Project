import React from "react";
import { useTranslation } from "react-i18next";
import { useAviation } from "../../hooks/useAviation";
import { WorkspaceShell } from "../../layouts/WorkspaceShell";
import { AviationOverviewStrip } from "./AviationOverviewStrip";
import { AviationRegistry } from "./AviationRegistry";
import { AviationPremiumModule } from "./AviationPremiumModule";
import { AviationRegionalModule } from "./AviationRegionalModule";

export default function AviationWorkspace() {
  const { t } = useTranslation("aviation");
  const { airlines, airports, metadata, premium, regions, loading } = useAviation();

  return (
    <WorkspaceShell
      id="aviation"
      accent="signal"
      className="workspace-aviation"
      title={t("pageTitle")}
      subtitle={t("pageSubtitle")}
    >
      <div className="forecasting-grid aviation-grid">
        <section className="fg-cell fg-span-12">
          <AviationOverviewStrip
            metadata={metadata}
            airlines={airlines}
            airports={airports}
            loading={loading}
          />
        </section>

        <section className="fg-cell fg-span-12">
          <AviationRegistry airlines={airlines} loading={loading} />
        </section>

        <section className="fg-cell fg-span-6">
          <AviationPremiumModule premium={premium} loading={loading} />
        </section>

        <section className="fg-cell fg-span-6">
          <AviationRegionalModule regions={regions} loading={loading} />
        </section>
      </div>
    </WorkspaceShell>
  );
}
