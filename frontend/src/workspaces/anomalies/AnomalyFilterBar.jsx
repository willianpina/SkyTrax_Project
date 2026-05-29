import React, { memo } from "react";
import { useTranslation } from "react-i18next";
import { SEV_ORDER } from "./anomalyShared";

function AnomalyFilterBarInner({ counts, sevFilter, onFilterChange }) {
  const { t } = useTranslation(["anomalies"]);

  return (
    <div className="anomaly-filter-bar" role="toolbar" aria-label={t("filter.toolbar", { defaultValue: "Severity filters" })}>
      <button
        type="button"
        className={`anomaly-filter-btn ${!sevFilter ? "anomaly-filter-btn--active" : ""}`}
        onClick={() => onFilterChange(null)}
      >
        {t("filter.all")}
      </button>
      {SEV_ORDER.map((s) => (
        <button
          key={s}
          type="button"
          className={`anomaly-filter-btn anomaly-filter-btn--${s} ${sevFilter === s ? "anomaly-filter-btn--active" : ""}`}
          onClick={() => onFilterChange(sevFilter === s ? null : s)}
        >
          {t(`filter.${s}`)} ({counts[s]})
        </button>
      ))}
    </div>
  );
}

export const AnomalyFilterBar = memo(AnomalyFilterBarInner);
