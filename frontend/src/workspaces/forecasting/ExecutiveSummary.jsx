import React, { memo } from "react";
import { useTranslation } from "react-i18next";
import { Activity, TrendingDown, TrendingUp, Shield, AlertTriangle, Brain } from "lucide-react";
import { OperationalModuleCard } from "../../components/forecasting/OperationalModuleCard";
import { formatScore, formatPercent, formatDeltaNumeric } from "../../utils/formatMetric";

function ExecutiveSummaryInner({ summary }) {
  const { t } = useTranslation(["charts", "common"]);

  const cards = [
    {
      icon: Activity,
      label: t("charts:executive.monitored", { defaultValue: "Monitored" }),
      value: summary.total,
      accent: "signal",
    },
    {
      icon: TrendingDown,
      label: t("charts:executive.deteriorating", { defaultValue: "Deteriorating" }),
      value: summary.deteriorating,
      accent: summary.deteriorating > 0 ? "risk" : "muted",
    },
    {
      icon: TrendingUp,
      label: t("charts:executive.recovering", { defaultValue: "Recovering" }),
      value: summary.recovering,
      accent: summary.recovering > 0 ? "positive" : "muted",
    },
    {
      icon: Shield,
      label: t("charts:executive.globalRisk", { defaultValue: "Global Risk" }),
      value: t(`common:severity.${summary.avgRisk}`, { defaultValue: summary.avgRisk }),
      accent:
        summary.avgRisk === "critical" || summary.avgRisk === "high"
          ? "risk"
          : summary.avgRisk === "medium"
            ? "warning"
            : "positive",
    },
    {
      icon: AlertTriangle,
      label: t("charts:executive.topAlert", { defaultValue: "Top Alert" }),
      value: summary.topAlert?.airline || "—",
      sub: summary.topAlert ? `Δ ${formatDeltaNumeric(summary.topAlert.scoreDelta)}` : null,
      accent: summary.topAlert ? "risk" : "muted",
    },
    {
      icon: Brain,
      label: t("charts:executive.modelConfidence", { defaultValue: "Model Confidence" }),
      value: formatPercent(summary.avgConfidence, { allowZero: true }),
      accent:
        summary.avgConfidence >= 70 ? "positive" : summary.avgConfidence >= 45 ? "warning" : "risk",
    },
  ];

  return (
    <OperationalModuleCard
      className="forecast-kpi-module"
      title={t("charts:executive.stripLabel", { defaultValue: "Forecast intelligence" })}
      subtitle={t("charts:executive.stripSubtitle", { defaultValue: "Portfolio runtime summary" })}
      bodyClassName="forecast-kpi-module__body"
    >
      <div className="forecast-executive-strip">
        {cards.map((card) => (
          <div key={card.label} className={`exec-card exec-card--${card.accent}`}>
            <div className="exec-card-icon">
              <card.icon size={16} strokeWidth={1.5} />
            </div>
            <div className="exec-card-body">
              <span className="exec-card-label">{card.label}</span>
              <span className="exec-card-value">{card.value}</span>
              {card.sub && <span className="exec-card-sub">{card.sub}</span>}
            </div>
          </div>
        ))}
      </div>
    </OperationalModuleCard>
  );
}

export const ExecutiveSummary = memo(ExecutiveSummaryInner);
