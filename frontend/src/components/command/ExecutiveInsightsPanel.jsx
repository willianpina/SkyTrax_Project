import React, { memo } from "react";
import { useTranslation } from "react-i18next";
import { PanelShell, ConfidenceBadge, SeverityBadge } from "../ui/PanelShell";

function ExecutiveInsightsPanelInner({ insights, defaultInsight }) {
  const { t } = useTranslation(["dashboard", "common"]);
  const rows = insights?.length ? insights : [defaultInsight];

  return (
    <PanelShell
      title={t("sections.executiveInsights")}
      subtitle={t("sections.signals", { count: insights?.length || 0 })}
      accent="warning"
      expandable
      defaultExpanded={insights?.length > 0}
      className="insights-panel span-wide"
    >
      <div className="insight-grid">
        {rows.map((insight) => (
          <div className={`insight-card hover-intel severity-${insight.severity}`} key={`${insight.airline}-${insight.summary}`}>
            <div className="insight-card-head">
              <strong style={{ fontSize: "12px" }}>{insight.airline}</strong>
              <SeverityBadge severity={insight.severity} />
              {insight.confidence != null && (
                <ConfidenceBadge score={Math.round(insight.confidence * 100)} />
              )}
            </div>
            <p>{insight.summary || insight.insight_text}</p>
            {insight.category && <span className="op-tag">{insight.category}</span>}
            {(insight.drivers || insight.supporting_topics || []).length > 0 && (
              <div className="insight-drivers">
                {(insight.drivers || insight.supporting_topics || []).slice(0, 4).map((d) => (
                  <span className="op-tag" key={d}>{d}</span>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>
    </PanelShell>
  );
}

export const ExecutiveInsightsPanel = memo(ExecutiveInsightsPanelInner);
