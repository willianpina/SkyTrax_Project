import React from "react";
import { useTranslation } from "react-i18next";
import { useSharedAnalytics } from "../../hooks/AnalyticsProvider";
import { WorkspaceShell } from "../../layouts/WorkspaceShell";
import { SemanticInvestigationPanel } from "../../components/command/SemanticInvestigationPanel";
import { TopicPanel } from "../../components/TopicPanel";
import { FrictionMatrix } from "../../components/FrictionMatrix";

export default function SemanticWorkspace() {
  const { t } = useTranslation(["semantic", "charts", "dashboard", "nav"]);
  const { data, clusters, reputation, apiBase } = useSharedAnalytics();

  return (
    <WorkspaceShell id="semantic" title={t("nav:nav.semantic")} subtitle={t("semantic:lookup.subtitle")} accent="signal">
      <SemanticInvestigationPanel clusters={clusters} apiBase={apiBase} reputation={reputation} />

      <section className="tactical-grid">
        <TopicPanel title={t("dashboard:topics.positiveDrivers")} rows={data.top_positive_topics || []} tone="positive" />
        <TopicPanel title={t("dashboard:topics.negativeFriction")} rows={data.top_negative_topics || []} tone="negative" />
      </section>

      <FrictionMatrix />
    </WorkspaceShell>
  );
}
