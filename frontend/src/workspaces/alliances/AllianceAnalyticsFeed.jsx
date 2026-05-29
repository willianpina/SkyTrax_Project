import React, { memo, useMemo } from "react";
import { useTranslation } from "react-i18next";
import { Radio, Zap } from "lucide-react";
import { OperationalModuleCard } from "../../components/forecasting/OperationalModuleCard";
import { SeverityBadge } from "../../components/ui/PanelShell";
import { buildAnalyticsFeedItems } from "./allianceShared";

function AllianceAnalyticsFeedInner({ alliances, fusionSignals, loading }) {
  const { t } = useTranslation("alliances");
  const items = useMemo(
    () => buildAnalyticsFeedItems(alliances, fusionSignals, t),
    [alliances, fusionSignals, t]
  );
  const hasItems = items.length > 0;

  const status = (
    <>
      <span className="op-status-pill">
        <Zap size={12} aria-hidden />
        {hasItems ? t("feedSignals", { count: items.length }) : t("badgeRuntime")}
      </span>
      <span className="op-status-pill op-status-pill--muted">
        <Radio size={12} aria-hidden />
        {t("badgeNetwork")}
      </span>
    </>
  );

  return (
    <OperationalModuleCard
      className="alliance-feed-module"
      title={t("feedTitle")}
      subtitle={hasItems ? t("feedSubtitle") : t("feedSubtitleEmpty")}
      status={status}
      expandable
      defaultExpanded
      bodyClassName="alliance-feed-module__body"
    >
      {loading && !hasItems ? (
        <div className="alliance-module-skeleton" />
      ) : !hasItems ? (
        <div className="alliance-empty-runtime alliance-empty-runtime--compact">
          <Zap size={18} strokeWidth={1.2} aria-hidden />
          <p className="alliance-empty-runtime__title">{t("feedEmptyTitle")}</p>
          <p className="alliance-empty-runtime__detail">{t("feedEmptyDetail")}</p>
        </div>
      ) : (
        <ul className="insight-signal-stream alliance-insight-stream" role="list">
          {items.map((item) => {
            const sev = (item.severity || "neutral").toLowerCase();
            return (
              <li
                className={`insight-signal-card alliance-insight-card severity-${sev}`}
                key={item.id}
                role="listitem"
              >
                <div className="insight-signal-head alliance-insight-head">
                  <strong className="insight-signal-airline">{item.alliance}</strong>
                  <SeverityBadge severity={sev === "low" ? "good" : sev} />
                </div>
                <p className="insight-signal-copy">{item.title}</p>
                <footer className="insight-signal-footer alliance-insight-footer">
                  <span className="insight-signal-time">{item.detail}</span>
                  <span className="alliance-insight-metric">{item.metric}</span>
                </footer>
              </li>
            );
          })}
        </ul>
      )}
    </OperationalModuleCard>
  );
}

export const AllianceAnalyticsFeed = memo(AllianceAnalyticsFeedInner);
