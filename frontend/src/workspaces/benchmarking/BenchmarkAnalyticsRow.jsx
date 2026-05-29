import React, { memo, useMemo } from "react";
import { useTranslation } from "react-i18next";
import { buildComplaintDensityOption } from "../../lib/chartConfigs";
import { OperationalModuleCard } from "../../components/forecasting/OperationalModuleCard";
import { BenchmarkingRadar } from "../../components/charts/BenchmarkingRadar";
import { ChartPanel } from "../../components/charts/ChartPanel";

function BenchmarkAnalyticsRowInner({ reputation, benchmarking }) {
  const { t } = useTranslation(["benchmarking", "charts"]);

  const complaintOption = useMemo(
    () => buildComplaintDensityOption(reputation, benchmarking?.complaint_density),
    [reputation, benchmarking?.complaint_density]
  );

  return (
    <OperationalModuleCard
      className="benchmark-analytics-module"
      title={t("analytics.title", { defaultValue: "Comparative analytics" })}
      subtitle={t("analytics.subtitle", {
        defaultValue: "Multi-dimensional peer benchmarking and complaint density",
      })}
      bodyClassName="benchmark-analytics-module__grid"
    >
      <div className="op-module-pane op-module-pane--chart">
        <BenchmarkingRadar radarRows={benchmarking?.radar_analytics} embedded />
      </div>
      <div className="op-module-pane op-module-pane--chart">
        <ChartPanel
          embedded
          variant="executive"
          title={t("charts:complaintDensity.title")}
          subtitle={t("charts:complaintDensity.subtitle")}
          option={complaintOption}
          accent="risk"
          height={240}
          emptyMessage={t("analytics.complaintEmpty", { defaultValue: "Complaint density populates with indexed reviews." })}
        />
      </div>
    </OperationalModuleCard>
  );
}

export const BenchmarkAnalyticsRow = memo(BenchmarkAnalyticsRowInner);
