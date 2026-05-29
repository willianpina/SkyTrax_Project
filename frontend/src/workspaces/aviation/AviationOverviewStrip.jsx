import React, { memo } from "react";
import { useTranslation } from "react-i18next";
import { Building2, Crown, MapPin, Plane, Shield, TrendingDown } from "lucide-react";
import { OperationalModuleCard } from "../../components/forecasting/OperationalModuleCard";
import { resolveMetric } from "./aviationShared";

function AviationOverviewStripInner({ metadata, airlines, airports, loading }) {
  const { t } = useTranslation("aviation");
  const hasData =
    resolveMetric(metadata?.airlines_total, airlines.length) > 0 ||
    resolveMetric(metadata?.airports_total, airports.length) > 0;

  const status = (
    <>
      <span className="op-status-pill">
        <Plane size={12} aria-hidden />
        {t("badgeRuntime")}
      </span>
      <span className={`op-status-pill ${hasData || loading ? "" : "op-status-pill--muted"}`}>
        <Shield size={12} aria-hidden />
        {hasData ? t("badgeIngestion") : t("badgeIngestionStandby")}
      </span>
    </>
  );

  const stats = [
    {
      icon: Plane,
      label: t("statAirlines"),
      hint: t("statAirlinesHint"),
      value: resolveMetric(metadata?.airlines_total, airlines.length),
    },
    {
      icon: MapPin,
      label: t("statAirports"),
      hint: t("statAirportsHint"),
      value: resolveMetric(metadata?.airports_total, airports.length),
    },
    {
      icon: Shield,
      label: t("statAlliances"),
      hint: t("statAlliancesHint"),
      value: resolveMetric(metadata?.alliances_total),
    },
    {
      icon: Building2,
      label: t("statHubs"),
      hint: t("statHubsHint"),
      value: resolveMetric(metadata?.hubs_total),
    },
    {
      icon: Crown,
      label: t("statPremium"),
      hint: t("statPremiumHint"),
      value: resolveMetric(metadata?.premium_airlines),
    },
    {
      icon: TrendingDown,
      label: t("statLowCost"),
      hint: t("statLowCostHint"),
      value: resolveMetric(metadata?.low_cost_airlines),
    },
  ];

  return (
    <OperationalModuleCard
      className="aviation-overview-module"
      status={status}
      bodyClassName="aviation-overview-module__body"
    >
      <div className="aviation-summary-bar">
        {stats.map(({ icon: Icon, label, hint, value }) => (
          <div className="aviation-summary-stat" key={label}>
            <div className="aviation-summary-stat-top">
              <Icon size={13} aria-hidden />
              <span className="aviation-summary-label">{label}</span>
            </div>
            <span className="aviation-summary-value">{loading && !value ? "—" : value}</span>
            <span className="aviation-summary-hint">{hint}</span>
          </div>
        ))}
      </div>
    </OperationalModuleCard>
  );
}

export const AviationOverviewStrip = memo(AviationOverviewStripInner);
