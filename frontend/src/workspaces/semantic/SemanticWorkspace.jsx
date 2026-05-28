import React from "react";
import { useTranslation } from "react-i18next";
import { useSharedAnalytics } from "../../hooks/AnalyticsProvider";
import { WorkspaceShell } from "../../layouts/WorkspaceShell";
import { SemanticOverviewStrip } from "./SemanticOverviewStrip";
import { SemanticTopicsPanel } from "./SemanticTopicsPanel";
import { SemanticFrictionModule } from "./SemanticFrictionModule";
import { SemanticEntityRuntime } from "./SemanticEntityRuntime";

export default function SemanticWorkspace() {
  const { t } = useTranslation("semantic");
  const { data, clusters, reputation, apiBase } = useSharedAnalytics();

  const positive = data?.top_positive_topics || [];
  const negative = data?.top_negative_topics || [];

  return (
    <WorkspaceShell
      id="semantic"
      accent="signal"
      className="workspace-semantic"
      title={t("pageTitle")}
      subtitle={t("pageSubtitle")}
    >
      <div className="forecasting-grid semantic-grid semantic-grid--calm">
        <section className="fg-cell fg-span-12">
          <SemanticOverviewStrip clusters={clusters} positive={positive} negative={negative} />
        </section>

        <section className="fg-cell fg-span-12">
          <SemanticTopicsPanel positive={positive} negative={negative} />
        </section>

        <section className="fg-cell fg-span-12">
          <SemanticFrictionModule />
        </section>

        <section className="fg-cell fg-span-12">
          <SemanticEntityRuntime clusters={clusters} apiBase={apiBase} reputation={reputation} />
        </section>
      </div>
    </WorkspaceShell>
  );
}
