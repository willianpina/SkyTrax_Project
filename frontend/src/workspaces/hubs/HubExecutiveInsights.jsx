import React, { memo, useMemo } from "react";
import { useTranslation } from "react-i18next";
import { Brain, Zap } from "lucide-react";
import { OperationalModuleCard } from "../../components/forecasting/OperationalModuleCard";
import { SeverityBadge } from "../../components/ui/PanelShell";
import { buildHubInsights } from "./hubsShared";

function HubExecutiveInsightsInner({ rankings, concentration, dashboard, loading }) {
  const { t } = useTranslation("hubs");
  const items = useMemo(
    () => buildHubInsights(rankings, concentration, dashboard, t),
    [rankings, concentration, dashboard, t]
  );
  const hasItems = items.length > 0;

  const status = (
    <>
      <span className="op-status-pill">
        <Zap size={12} aria-hidden />
        {hasItems ? items.length : t("badgeRuntime")}
      </span>
      <span className="op-status-pill op-status-pill--muted">
        <Brain size={12} aria-hidden />
        {t("insightsTitle")}
      </span>
    </>
  );

  return (
    <OperationalModuleCard
      className="hub-insights-module"
      title={t("insightsTitle")}
      subtitle={hasItems ? t("insightsSubtitle") : t("insightsSubtitleEmpty")}
      status={status}
      expandable
      defaultExpanded
      bodyClassName="hub-insights-module__body"
    >
      {loading && !hasItems ? (
        <div className="hub-module-skeleton" />
      ) : !hasItems ? (
        <div className="hub-empty-runtime hub-empty-runtime--compact">
          <Brain size={18} strokeWidth={1.2} aria-hidden />
          <p className="hub-empty-runtime__title">{t("emptyHubTitle")}</p>
          <p className="hub-empty-runtime__detail">{t("emptyHubDetail")}</p>
        </div>
      ) : (
        <ul className="insight-signal-stream hub-insight-stream" role="list">
          {items.map((item) => {
            const sev = (item.severity || "neutral").toLowerCase();
            return (
              <li
                className={`insight-signal-card hub-insight-card severity-${sev}`}
                key={item.id}
                role="listitem"
              >
                <div className="insight-signal-head hub-insight-head">
                  <strong className="insight-signal-airline">{item.hub}</strong>
                  <SeverityBadge severity={sev === "low" ? "good" : sev} />
                </div>
                <p className="insight-signal-copy">{item.title}</p>
                <footer className="insight-signal-footer hub-insight-footer">
                  <span className="insight-signal-time">{item.detail}</span>
                  <span className="hub-insight-metric">{item.metric}</span>
                </footer>
              </li>
            );
          })}
        </ul>
      )}
    </OperationalModuleCard>
  );
}

export const HubExecutiveInsights = memo(HubExecutiveInsightsInner);
