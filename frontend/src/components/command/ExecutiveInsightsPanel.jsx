import React, { memo } from "react";
import { useTranslation } from "react-i18next";
import { formatScore } from "../../utils/formatMetric";
import { PanelShell, ConfidenceBadge, SeverityBadge } from "../ui/PanelShell";

function ExecutiveInsightsPanelInner({ insights, defaultInsight }) {
  const { t } = useTranslation(["dashboard", "common"]);
  const hasInsights = (insights?.length || 0) > 0;
  const rows = hasInsights ? insights : [];

  return (
    <PanelShell
      title={t("sections.executiveInsights")}
      subtitle={hasInsights ? t("sections.signals", { count: insights.length }) : "Operational insight stream standby"}
      accent="warning"
      expandable
      defaultExpanded={hasInsights}
      quiet
      className={`insights-panel span-wide ${hasInsights ? "" : "insights-panel--compact"}`.trim()}
    >
      {!hasInsights && (
        <div className="muted-copy insights-empty-copy">
          <p>No executive signals above confidence threshold.</p>
          <p>Signal cards expand automatically once runtime correlation confidence stabilizes.</p>
        </div>
      )}
      <ul className="insight-feed" role="list">
        {rows.map((insight) => (
          <li className={`insight-feed-row severity-${insight.severity}`} key={`${insight.airline}-${insight.summary}`}>
            <div className="insight-feed-head">
              <strong className="insight-feed-airline">{insight.airline}</strong>
              <div className="insight-feed-meta">
                <SeverityBadge severity={insight.severity} />
                {insight.confidence != null && (
                  <ConfidenceBadge score={Math.round(Number(insight.confidence) * 100)} />
                )}
              </div>
            </div>
            <p className="insight-feed-copy">{insight.summary || insight.insight_text}</p>
            {(insight.category || (insight.drivers || insight.supporting_topics || []).length > 0) && (
              <div className="insight-feed-tags">
                {insight.category && <span className="insight-feed-tag">{insight.category}</span>}
                {(insight.drivers || insight.supporting_topics || []).slice(0, 4).map((d) => (
                  <span className="insight-feed-tag" key={d}>{d}</span>
                ))}
              </div>
            )}
          </li>
        ))}
      </ul>
    </PanelShell>
  );
}

export const ExecutiveInsightsPanel = memo(ExecutiveInsightsPanelInner);
