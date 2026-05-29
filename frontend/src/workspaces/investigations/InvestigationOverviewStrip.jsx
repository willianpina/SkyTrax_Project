import React, { memo } from "react";
import { useTranslation } from "react-i18next";
import { AlertTriangle, Brain, FileSearch, Shield } from "lucide-react";
import { OperationalModuleCard } from "../../components/forecasting/OperationalModuleCard";
import { investigationMetrics } from "./investigationsShared";

function InvestigationOverviewStripInner({ anomalies, insights, selectedAirline, reputation }) {
  const { t } = useTranslation("investigations");
  const m = investigationMetrics(anomalies, insights, selectedAirline, reputation);

  const status = (
    <>
      <span className="op-status-pill">
        <FileSearch size={12} aria-hidden />
        {t("badgeRuntime")}
      </span>
      <span className="op-status-pill op-status-pill--muted">
        <Brain size={12} aria-hidden />
        {t("badgeCorrelation")}
      </span>
    </>
  );

  const stats = [
    { icon: AlertTriangle, label: t("statActive"), hint: t("statActiveHint"), value: m.activeIncidents },
    { icon: Shield, label: t("statCarriers"), hint: t("statCarriersHint"), value: m.carriersImpacted },
    { icon: FileSearch, label: t("statCritical"), hint: t("statCriticalHint"), value: m.criticalCases },
    { icon: Brain, label: t("statInsights"), hint: t("statInsightsHint"), value: m.correlatedInsights },
  ];

  return (
    <OperationalModuleCard className="investigation-overview-module" status={status} bodyClassName="investigation-overview-module__body">
      <div className="investigation-summary-bar">
        {stats.map(({ icon: Icon, label, hint, value }) => (
          <div className="investigation-summary-stat" key={label}>
            <div className="investigation-summary-stat-top">
              <Icon size={13} aria-hidden />
              <span className="investigation-summary-label">{label}</span>
            </div>
            <span className="investigation-summary-value">{value}</span>
            <span className="investigation-summary-hint">{hint}</span>
          </div>
        ))}
      </div>
    </OperationalModuleCard>
  );
}

export const InvestigationOverviewStrip = memo(InvestigationOverviewStripInner);
