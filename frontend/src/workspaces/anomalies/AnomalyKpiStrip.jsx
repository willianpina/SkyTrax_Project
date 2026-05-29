import React, { memo } from "react";
import { useTranslation } from "react-i18next";
import {
  AlertTriangle, Zap, Activity, Radio, Shield, BarChart3,
} from "lucide-react";
import { OperationalModuleCard } from "../../components/forecasting/OperationalModuleCard";

function AnomalyKpiStripInner({ counts, total, carriersAffected }) {
  const { t } = useTranslation(["anomalies"]);

  const cells = [
    {
      icon: AlertTriangle,
      label: t("strip.activeSignals"),
      value: total,
      sub: t("strip.activeSignalsSub"),
      alert: total > 0,
    },
    {
      icon: Zap,
      label: t("strip.critical"),
      value: counts.critical + counts.high,
      sub: t("strip.criticalSub"),
      alert: counts.critical + counts.high > 0,
    },
    {
      icon: Activity,
      label: t("strip.medium"),
      value: counts.medium,
      sub: t("strip.mediumSub"),
      alert: counts.medium > 0,
    },
    {
      icon: Radio,
      label: t("strip.lowPriority"),
      value: counts.low,
      sub: t("strip.lowPrioritySub"),
      alert: false,
    },
    {
      icon: Shield,
      label: t("strip.carriers"),
      value: carriersAffected,
      sub: t("strip.carriersSub"),
      alert: carriersAffected > 0,
    },
    {
      icon: BarChart3,
      label: t("strip.detection"),
      value: total > 0 ? "Live" : "—",
      sub: t("strip.detectionSub"),
      alert: false,
    },
  ];

  return (
    <OperationalModuleCard
      className="anomaly-kpi-module"
      title={t("runtime.pageTitle", { defaultValue: "Anomaly intelligence" })}
      subtitle={t("runtime.pageSubtitle", { defaultValue: "Operational threat monitoring and detection runtime" })}
      meta={
        <span className="op-module-count">
          {t("subtitle", { count: total })}
        </span>
      }
      bodyClassName="anomaly-kpi-module__body"
    >
      <div className="anomaly-kpi-grid">
        {cells.map(({ icon: Icon, label, value, sub, alert }) => (
          <div
            key={label}
            className={`anomaly-kpi-cell ${alert ? "anomaly-kpi-cell--alert" : ""}`}
          >
            <div className="anomaly-kpi-cell-top">
              <Icon size={13} aria-hidden />
              <span className="anomaly-kpi-cell-label">{label}</span>
            </div>
            <span className="anomaly-kpi-cell-value">{value}</span>
            <span className="anomaly-kpi-cell-sub">{sub}</span>
          </div>
        ))}
      </div>
    </OperationalModuleCard>
  );
}

export const AnomalyKpiStrip = memo(AnomalyKpiStripInner);
