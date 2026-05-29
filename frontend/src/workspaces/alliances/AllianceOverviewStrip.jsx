import React, { memo } from "react";
import { useTranslation } from "react-i18next";
import { AlertTriangle, Globe, MapPin, Radio, Star, Users } from "lucide-react";
import { OperationalModuleCard } from "../../components/forecasting/OperationalModuleCard";
import { formatScore } from "../../utils/formatMetric";
import { allianceOverviewMetrics, riskLevel } from "./allianceShared";

function AllianceOverviewStripInner({ alliances, hubAlliances, loading }) {
  const { t } = useTranslation("alliances");
  const m = allianceOverviewMetrics(alliances, hubAlliances);
  const hasData = (alliances || []).length > 0;
  const riskTone = riskLevel(m.avgRisk);

  const status = (
    <>
      <span className="op-status-pill">
        <Globe size={12} aria-hidden />
        {t("badgeRuntime")}
      </span>
      <span className={`op-status-pill ${hasData || loading ? "" : "op-status-pill--muted"}`}>
        <Radio size={12} aria-hidden />
        {hasData ? t("badgeNetwork") : t("badgeRuntime")}
      </span>
    </>
  );

  const stats = [
    {
      icon: Globe,
      label: t("statAlliances"),
      hint: t("statAlliancesHint"),
      value: loading && !hasData ? "—" : m.allianceCount || "—",
    },
    {
      icon: Users,
      label: t("statMembers"),
      hint: t("statMembersHint"),
      value: loading && !hasData ? "—" : m.totalMembers.toLocaleString(),
    },
    {
      icon: MapPin,
      label: t("statAllianceHubs"),
      hint: t("statAllianceHubsHint"),
      value: loading && m.allianceHubCount === 0 ? "—" : m.allianceHubCount.toLocaleString(),
    },
    {
      icon: Radio,
      label: t("statReviews"),
      hint: t("statReviewsHint"),
      value: loading && !hasData ? "—" : m.totalReviews.toLocaleString(),
    },
    {
      icon: Star,
      label: t("statBest"),
      hint: t("statBestHint"),
      value: loading && !hasData ? "—" : formatScore(m.bestRating),
      trend: hasData ? m.bestAlliance : null,
    },
    {
      icon: AlertTriangle,
      label: t("statRisk"),
      hint: t("statRiskHint"),
      value: loading && !hasData ? "—" : formatScore(m.avgRisk),
      tone: riskTone,
      trend: hasData
        ? riskTone === "low"
          ? "↓"
          : riskTone === "high"
            ? "↑"
            : "→"
        : null,
    },
  ];

  return (
    <OperationalModuleCard
      className="alliance-overview-module"
      status={status}
      bodyClassName="alliance-overview-module__body"
    >
      <div className="alliance-summary-bar">
        {stats.map(({ icon: Icon, label, hint, value, trend, tone }) => (
          <div
            className={`alliance-summary-stat${tone ? ` alliance-summary-stat--${tone}` : ""}`}
            key={label}
          >
            <div className="alliance-summary-stat-top">
              <Icon size={13} aria-hidden />
              <span className="alliance-summary-label">{label}</span>
            </div>
            <span className="alliance-summary-value">{value}</span>
            <span className="alliance-summary-hint">{trend || hint}</span>
          </div>
        ))}
      </div>
    </OperationalModuleCard>
  );
}

export const AllianceOverviewStrip = memo(AllianceOverviewStripInner);
