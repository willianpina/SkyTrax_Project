import React, { memo, useMemo } from "react";
import { useTranslation } from "react-i18next";
import { BarChart3 } from "lucide-react";
import { OperationalModuleCard } from "../../components/forecasting/OperationalModuleCard";
import { formatScore } from "../../utils/formatMetric";
import { ALLIANCE_THEME, heatmapCells, sortAlliances } from "./allianceShared";

const METRIC_KEYS = ["reputation", "sentiment", "complaints", "risk"];

function AllianceComparisonPanelInner({ alliances, loading }) {
  const { t } = useTranslation("alliances");
  const sorted = sortAlliances(alliances);
  const isEmpty = !loading && sorted.length === 0;

  const labels = {
    reputation: t("compareReputation"),
    sentiment: t("compareSentiment"),
    complaints: t("compareComplaints"),
    risk: t("compareRisk"),
  };

  const rows = useMemo(() => {
    return sorted.map((a) => {
      const cells = heatmapCells(a);
      const ratingNorm = Math.min(100, ((a.avg_rating || 0) / 10) * 100);
      return {
        id: a.id || a.name,
        name: a.name,
        accent: ALLIANCE_THEME[a.name]?.accent || "#94a3b8",
        metrics: {
          reputation: ratingNorm,
          sentiment: cells.sentiment,
          complaints: cells.complaints,
          risk: cells.risk,
        },
      };
    });
  }, [sorted]);

  const maxByMetric = useMemo(() => {
    const max = {};
    METRIC_KEYS.forEach((key) => {
      max[key] = Math.max(1, ...rows.map((r) => r.metrics[key] || 0));
    });
    return max;
  }, [rows]);

  return (
    <OperationalModuleCard
      className="alliance-compare-module"
      title={t("compareTitle")}
      subtitle={t("compareSubtitle")}
      expandable
      defaultExpanded={rows.length > 0}
      bodyClassName="alliance-compare-module__body"
    >
      {loading && isEmpty ? (
        <div className="alliance-module-skeleton" />
      ) : isEmpty ? (
        <div className="alliance-empty-runtime alliance-empty-runtime--compact">
          <BarChart3 size={18} strokeWidth={1.2} aria-hidden />
          <p className="alliance-empty-runtime__title">{t("emptyTitle")}</p>
          <p className="alliance-empty-runtime__detail">{t("emptyDetail")}</p>
        </div>
      ) : (
        <div className="alliance-compare-chart">
          <div className="alliance-compare-legend" aria-hidden>
            {METRIC_KEYS.map((key) => (
              <span className="alliance-compare-legend-item" key={key}>
                {labels[key]}
              </span>
            ))}
          </div>
          {rows.map((row) => (
            <div className="alliance-compare-group" key={row.id}>
              <div className="alliance-compare-group-head">
                <span className="alliance-compare-dot" style={{ background: row.accent }} aria-hidden />
                <strong>{row.name}</strong>
              </div>
              {METRIC_KEYS.map((key) => {
                const val = row.metrics[key] || 0;
                const pct = (val / maxByMetric[key]) * 100;
                const tone =
                  key === "risk" || key === "complaints"
                    ? val > 50
                      ? "risk"
                      : val > 30
                        ? "warn"
                        : "good"
                    : val >= 70
                      ? "good"
                      : val >= 40
                        ? "warn"
                        : "risk";
                return (
                  <div className="alliance-compare-row" key={`${row.id}-${key}`}>
                    <span className="alliance-compare-metric-label">{labels[key]}</span>
                    <div className="alliance-compare-track" aria-hidden>
                      <div
                        className={`alliance-compare-fill alliance-compare-fill--${tone}`}
                        style={{ width: `${pct}%`, backgroundColor: row.accent }}
                      />
                    </div>
                    <span className="alliance-compare-value">{formatScore(val, { allowZero: true })}</span>
                  </div>
                );
              })}
            </div>
          ))}
        </div>
      )}
    </OperationalModuleCard>
  );
}

export const AllianceComparisonPanel = memo(AllianceComparisonPanelInner);
