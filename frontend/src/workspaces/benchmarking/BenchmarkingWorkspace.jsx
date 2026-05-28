import React from "react";
import { useTranslation } from "react-i18next";
import { useSharedAnalytics } from "../../hooks/AnalyticsProvider";
import { WorkspaceShell } from "../../layouts/WorkspaceShell";
import { FrictionMatrix } from "../../components/FrictionMatrix";
import { OperationalModuleCard } from "../../components/forecasting/OperationalModuleCard";
import { BenchmarkKpiStrip } from "./BenchmarkKpiStrip";
import { BenchmarkAnalyticsRow } from "./BenchmarkAnalyticsRow";
import { BenchmarkRuntimeTable } from "./BenchmarkRuntimeTable";

export default function BenchmarkingWorkspace() {
  const { t } = useTranslation(["benchmarking", "semantic"]);
  const { reputation, benchmarking } = useSharedAnalytics();

  return (
    <WorkspaceShell id="benchmarking" accent="signal" className="workspace-benchmarking">
      <div className="forecasting-grid benchmarking-grid">
        <section className="fg-cell fg-span-12" aria-label={t("kpi.title", { defaultValue: "Benchmark KPIs" })}>
          <BenchmarkKpiStrip reputation={reputation} />
        </section>

        <section className="fg-cell fg-span-12" aria-label={t("analytics.title", { defaultValue: "Comparative analytics" })}>
          <BenchmarkAnalyticsRow reputation={reputation} benchmarking={benchmarking} />
        </section>

        <section className="fg-cell fg-span-12" aria-label={t("runtime.title", { defaultValue: "Benchmark runtime" })}>
          <BenchmarkRuntimeTable reputation={reputation} benchmarking={benchmarking} />
        </section>

        <section className="fg-cell fg-span-12 benchmark-deep-section" aria-label={t("deep.title", { defaultValue: "Deep analytics" })}>
          <OperationalModuleCard
            className="benchmark-friction-module"
            title={t("semantic:friction.title", { defaultValue: "Friction intelligence" })}
            subtitle={t("deep.subtitle", { defaultValue: "Topic-level operational friction heatmap" })}
          >
            <FrictionMatrix bare chartMaxHeight={360} />
          </OperationalModuleCard>
        </section>
      </div>
    </WorkspaceShell>
  );
}
