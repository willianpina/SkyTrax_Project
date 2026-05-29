import React, { memo } from "react";
import { useTranslation } from "react-i18next";
import { Brain, Sparkles } from "lucide-react";
import { OperationalModuleCard } from "../../components/forecasting/OperationalModuleCard";
import { semanticOverviewMetrics } from "./semanticShared";

function SemanticOverviewStripInner({ clusters, positive, negative }) {
  const { t } = useTranslation("semantic");
  const m = semanticOverviewMetrics({ clusters, positive, negative });

  const status = (
    <>
      <span className="op-status-pill">
        <Sparkles size={12} aria-hidden />
        {t("badgeRuntime")}
      </span>
      <span className={`op-status-pill ${m.pipelineActive ? "" : "op-status-pill--muted"}`}>
        <Brain size={12} aria-hidden />
        {m.pipelineActive ? t("badgeNlp") : t("badgeNlpStandby")}
      </span>
    </>
  );

  const stats = [
    { label: t("statClusters"), hint: t("statClustersHint"), value: m.clusterCount },
    { label: t("statCorpus"), hint: t("statCorpusHint"), value: m.reviewVolume.toLocaleString() },
    { label: t("statPositive"), hint: t("statPositiveHint"), value: m.positiveCount },
    { label: t("statNegative"), hint: t("statNegativeHint"), value: m.negativeCount },
  ];

  return (
    <OperationalModuleCard
      className="semantic-overview-module semantic-overview-module--minimal"
      status={status}
      bodyClassName="semantic-overview-module__body"
    >
      <div className="semantic-summary-bar">
        {stats.map((s) => (
          <div className="semantic-summary-stat" key={s.label}>
            <span className="semantic-summary-value">{s.value}</span>
            <span className="semantic-summary-label">{s.label}</span>
            <span className="semantic-summary-hint">{s.hint}</span>
          </div>
        ))}
      </div>
    </OperationalModuleCard>
  );
}

export const SemanticOverviewStrip = memo(SemanticOverviewStripInner);
