import React, { memo, useMemo } from "react";
import { useTranslation } from "react-i18next";
import { OperationalModuleCard } from "../../components/forecasting/OperationalModuleCard";
import { enrichTopicRows } from "./semanticShared";

function TopicList({ rows, tone, t }) {
  const enriched = useMemo(() => enrichTopicRows(rows), [rows]);

  if (!enriched.length) {
    return <p className="semantic-pane-empty muted-copy">{t("emptyDetail")}</p>;
  }

  return (
    <ul className="semantic-topic-list semantic-topic-list--minimal" role="list">
      {enriched.map((row) => (
        <li className={`semantic-topic-row semantic-topic-row--${tone}`} key={row.label} role="listitem">
          <div className="semantic-topic-row-top">
            <strong className="semantic-topic-label">{row.label}</strong>
            <span className="semantic-topic-mentions">{t("incidence", { count: row.samples })}</span>
          </div>
          <div className="semantic-weight-track" aria-hidden>
            <div
              className={`semantic-weight-fill semantic-weight-fill--${tone}`}
              style={{ width: `${row.pct}%` }}
            />
          </div>
        </li>
      ))}
    </ul>
  );
}

function SemanticTopicsPanelInner({ positive = [], negative = [] }) {
  const { t } = useTranslation("semantic");
  const hasData = positive.length > 0 || negative.length > 0;

  return (
    <OperationalModuleCard
      className="semantic-narrative-module"
      title={t("narrativeTitle")}
      subtitle={t("narrativeSubtitle")}
      expandable
      defaultExpanded={hasData}
      bodyClassName="semantic-narrative-module__body"
    >
      {!hasData ? (
        <div className="semantic-empty-runtime semantic-empty-runtime--minimal">
          <p className="semantic-empty-runtime__title">{t("emptyTitle")}</p>
          <p className="semantic-empty-runtime__detail">{t("emptyDetail")}</p>
        </div>
      ) : (
        <div className="semantic-topics-split">
          <div className="semantic-topics-pane">
            <h3 className="semantic-pane-title semantic-pane-title--positive">{t("positivePane")}</h3>
            <TopicList rows={positive} tone="positive" t={t} />
          </div>
          <div className="semantic-topics-pane">
            <h3 className="semantic-pane-title semantic-pane-title--negative">{t("negativePane")}</h3>
            <TopicList rows={negative} tone="negative" t={t} />
          </div>
        </div>
      )}
    </OperationalModuleCard>
  );
}

export const SemanticTopicsPanel = memo(SemanticTopicsPanelInner);
