import React, { memo } from "react";
import { useTranslation } from "react-i18next";
import { formatShortDate } from "../../utils/datetime";
import { formatScore, formatGap as fmtGap } from "../../utils/formatMetric";
import { categorizeAnomaly } from "./anomalyShared";

export const IncidentRow = memo(function IncidentRow({ anomaly: a, compact = false }) {
  const { t } = useTranslation(["anomalies"]);
  const sev = a.severity || "low";
  const typeName = (a.anomaly_type || "").replace(/_/g, " ");
  const categoryKey = categorizeAnomaly(a.anomaly_type);
  const category = t(`categories.${categoryKey}`);
  const gap = fmtGap(a.observed_value, a.expected_value);
  const sevLabel = t(`severity.${sev}`);

  return (
    <div className={`anm-incident anm-incident--runtime anm-incident--${sev} ${compact ? "anm-incident--compact" : ""}`}>
      <div className="anm-incident-lead">
        <span className={`anm-sev-dot anm-sev-dot--${sev}`} aria-hidden />
        <span className={`anm-sev-chip anm-sev-chip--${sev}`}>{sevLabel}</span>
      </div>
      <div className="anm-incident-primary">
        <span className="anm-incident-type">{typeName}</span>
        <span className="anm-incident-cat">{category}</span>
      </div>
      <div className="anm-incident-scores">
        <div className="anm-score-cell">
          <span className="anm-score-label">{t("registry.observed")}</span>
          <span className="anm-score-val metric-num">{formatScore(a.observed_value, { allowZero: true })}</span>
        </div>
        <div className="anm-score-cell">
          <span className="anm-score-label">{t("registry.threshold")}</span>
          <span className="anm-score-val anm-score-val--dim metric-num">
            {formatScore(a.expected_value, { allowZero: true })}
          </span>
        </div>
        {gap ? (
          <div className="anm-score-cell">
            <span className="anm-score-label">{t("registry.gap")}</span>
            <span
              className={`anm-score-val anm-score-gap ${parseFloat(gap) < 0 ? "anm-score-gap--neg" : "anm-score-gap--pos"}`}
            >
              {gap}
            </span>
          </div>
        ) : null}
      </div>
      <time className="anm-incident-time">{formatShortDate(a.detected_at)}</time>
    </div>
  );
});
