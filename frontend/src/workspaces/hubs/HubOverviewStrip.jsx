import React, { memo } from "react";
import { useTranslation } from "react-i18next";
import {
  AlertTriangle,
  MapPin,
  Plane,
  Radio,
  Shield,
  TrendingDown,
  Users,
} from "lucide-react";
import { OperationalModuleCard } from "../../components/forecasting/OperationalModuleCard";
import { formatScore } from "../../utils/formatMetric";

function HubOverviewStripInner({ dashboard, loading }) {
  const { t } = useTranslation("hubs");
  const d = dashboard || {};
  const hasData = (d.airports_monitored ?? 0) > 0;

  const status = (
    <>
      <span className="op-status-pill">
        <Plane size={12} aria-hidden />
        {t("badgeRuntime")}
      </span>
      <span className={`op-status-pill ${hasData || loading ? "" : "op-status-pill--muted"}`}>
        <Radio size={12} aria-hidden />
        {hasData ? t("badgeInfrastructure") : t("badgeRuntime")}
      </span>
    </>
  );

  const stats = [
    {
      icon: MapPin,
      label: t("statMonitored"),
      hint: t("statMonitoredHint"),
      value: loading && !hasData ? "—" : d.airports_monitored ?? 0,
    },
    {
      icon: Plane,
      label: t("statActive"),
      hint: t("statActiveHint"),
      value: loading && !hasData ? "—" : d.active_hubs ?? 0,
      trend: hasData ? `→ ${d.active_hubs ?? 0}` : null,
    },
    {
      icon: AlertTriangle,
      label: t("statCritical"),
      hint: t("statCriticalHint"),
      value: loading && !hasData ? "—" : d.critical_hubs ?? 0,
      tone: (d.critical_hubs ?? 0) > 0 ? "high" : "low",
      trend: (d.critical_hubs ?? 0) > 0 ? "↑" : "↓",
    },
    {
      icon: Shield,
      label: t("statHighRisk"),
      hint: t("statHighRiskHint"),
      value: loading && !hasData ? "—" : d.high_risk_airports ?? 0,
      tone: (d.high_risk_airports ?? 0) > 0 ? "medium" : "low",
      trend: (d.high_risk_airports ?? 0) > 0 ? "↑" : "→",
    },
    {
      icon: Users,
      label: t("statAlliance"),
      hint: t("statAllianceHint"),
      value: loading && !hasData ? "—" : `${d.alliance_coverage ?? 0}%`,
      trend: hasData ? `${d.alliance_coverage ?? 0}%` : null,
    },
    {
      icon: TrendingDown,
      label: t("statHhi"),
      hint: t("statHhiHint"),
      value: loading && !hasData ? "—" : formatScore(d.operational_concentration ?? 0, { allowZero: true }),
      trend: hasData ? "HHI" : null,
    },
  ];

  return (
    <OperationalModuleCard
      className="hub-overview-module"
      status={status}
      bodyClassName="hub-overview-module__body"
    >
      <div className="hub-summary-bar">
        {stats.map(({ icon: Icon, label, hint, value, trend, tone }) => (
          <div className={`hub-summary-stat${tone ? ` hub-summary-stat--${tone}` : ""}`} key={label}>
            <div className="hub-summary-stat-top">
              <Icon size={13} aria-hidden />
              <span className="hub-summary-label">{label}</span>
            </div>
            <span className="hub-summary-value">{value}</span>
            <span className="hub-summary-hint">{trend || hint}</span>
          </div>
        ))}
      </div>
    </OperationalModuleCard>
  );
}

export const HubOverviewStrip = memo(HubOverviewStripInner);
