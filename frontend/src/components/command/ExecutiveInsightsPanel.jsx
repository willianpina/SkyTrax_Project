import React, { memo, useMemo } from "react";
import { useTranslation } from "react-i18next";
import { Brain, Radio } from "lucide-react";
import { OperationalModuleCard } from "../forecasting/OperationalModuleCard";
import { SeverityBadge } from "../ui/PanelShell";
import { formatOperationalDateTime } from "../../utils/datetime";

function InsightTelemetryScore({ value }) {
  if (value == null || Number.isNaN(Number(value))) return null;
  const pct = Math.round(Number(value) <= 1 ? Number(value) * 100 : Number(value));
  return <span className="insight-signal-score">{pct}%</span>;
}

function ExecutiveInsightsPanelInner({ insights }) {
  const { t } = useTranslation(["dashboard", "common"]);
  const rows = useMemo(() => (insights?.length ? insights : []), [insights]);
  const hasInsights = rows.length > 0;

  const status = (
    <>
      <span className="op-status-pill">
        <Radio size={12} aria-hidden />
        {hasInsights
          ? t("sections.insightsRuntime", { defaultValue: "Correlation runtime active" })
          : t("sections.insightsStandby", { defaultValue: "Insight stream standby" })}
      </span>
      <span className="op-status-pill op-status-pill--muted">
        <Brain size={12} aria-hidden />
        {hasInsights
          ? t("sections.signals", { count: rows.length })
          : t("sections.signals", { count: 0 })}
      </span>
    </>
  );

  return (
    <OperationalModuleCard
      className={`executive-insights-module ${hasInsights ? "" : "executive-insights-module--standby"}`.trim()}
      title={t("sections.executiveInsights")}
      subtitle={
        hasInsights
          ? t("sections.insightsSubtitle", {
              defaultValue: "Strategic intelligence signals from operational correlation",
            })
          : t("sections.insightsSubtitleEmpty", {
              defaultValue: "Executive recommendations appear when confidence threshold is met",
            })
      }
      status={status}
      expandable
      defaultExpanded={hasInsights}
      bodyClassName="executive-insights-module__body"
    >
      {!hasInsights ? (
        <div className="insight-signal-empty muted-copy">
          <p>{t("sections.insightsEmptyTitle", { defaultValue: "No executive signals above confidence threshold." })}</p>
          <p>
            {t("sections.insightsEmptyDetail", {
              defaultValue: "Signal cards expand automatically once runtime correlation confidence stabilizes.",
            })}
          </p>
        </div>
      ) : (
        <ul className="insight-signal-stream" role="list">
          {rows.map((insight) => {
            const key = `${insight.airline}-${insight.summary || insight.insight_text}-${insight.timestamp || insight.created_at || ""}`;
            const sev = (insight.severity || "neutral").toLowerCase();
            const drivers = (insight.drivers || insight.supporting_topics || []).slice(0, 3);

            return (
              <li
                className={`insight-signal-card severity-${sev}`}
                key={key}
                role="listitem"
              >
                <div className="insight-signal-head">
                  <strong className="insight-signal-airline">{insight.airline}</strong>
                  <div className="insight-signal-meta">
                    <SeverityBadge severity={sev} />
                    <InsightTelemetryScore value={insight.confidence} />
                  </div>
                </div>
                <p className="insight-signal-copy">{insight.summary || insight.insight_text}</p>
                <footer className="insight-signal-footer">
                  {insight.category ? (
                    <span className="insight-signal-tag">{insight.category}</span>
                  ) : null}
                  {drivers.map((d) => (
                    <span className="insight-signal-tag" key={d}>
                      {d}
                    </span>
                  ))}
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

export const ExecutiveInsightsPanel = memo(ExecutiveInsightsPanelInner);
