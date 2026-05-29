import React, { memo, useMemo } from "react";
import { useTranslation } from "react-i18next";
import { Brain, Radio } from "lucide-react";
import { OperationalModuleCard } from "../../components/forecasting/OperationalModuleCard";
import { SeverityBadge } from "../../components/ui/PanelShell";
import { formatOperationalDateTime } from "../../utils/datetime";
import { filterByAirline } from "./investigationsShared";

function InvestigationInsightsPanelInner({ insights, selectedAirline, reputation }) {
  const { t } = useTranslation("investigations");
  const rows = useMemo(
    () => filterByAirline(insights, selectedAirline, reputation).slice(0, 12),
    [insights, selectedAirline, reputation]
  );
  const hasRows = rows.length > 0;

  const status = (
    <>
      <span className="op-status-pill">
        <Radio size={12} aria-hidden />
        {hasRows ? t("badgeCorrelation") : t("badgeRuntime")}
      </span>
      <span className="op-status-pill op-status-pill--muted">
        <Brain size={12} aria-hidden />
        {t("statInsights")}: {rows.length}
      </span>
    </>
  );

  return (
    <OperationalModuleCard
      className="investigation-insights-module"
      title={t("insightsTitle")}
      subtitle={hasRows ? t("insightsSubtitle") : t("insightsSubtitleEmpty")}
      status={status}
      expandable
      defaultExpanded={hasRows}
      bodyClassName="investigation-insights-module__body"
    >
      {!hasRows ? (
        <div className="investigation-empty-runtime investigation-empty-runtime--compact">
          <p className="investigation-empty-runtime__title">{t("insightsEmptyTitle")}</p>
          <p className="investigation-empty-runtime__detail">{t("insightsEmptyDetail")}</p>
        </div>
      ) : (
        <ul className="insight-signal-stream investigation-insight-stream" role="list">
          {rows.map((insight) => {
            const sev = (insight.severity || "neutral").toLowerCase();
            const key = `${insight.airline}-${insight.summary || insight.insight_text}-${insight.timestamp || ""}`;
            return (
              <li
                className={`insight-signal-card investigation-insight-card severity-${sev}`}
                key={key}
                role="listitem"
              >
                <div className="insight-signal-head investigation-insight-head">
                  <strong className="insight-signal-airline">{insight.airline}</strong>
                  <SeverityBadge severity={sev} />
                </div>
                <p className="insight-signal-copy">{insight.summary || insight.insight_text}</p>
                <footer className="insight-signal-footer">
                  <time className="insight-signal-time">
                    {formatOperationalDateTime(
                      insight.timestamp || insight.created_at || insight.detected_at
                    )}
                  </time>
                </footer>
              </li>
            );
          })}
        </ul>
      )}
    </OperationalModuleCard>
  );
}

export const InvestigationInsightsPanel = memo(InvestigationInsightsPanelInner);
