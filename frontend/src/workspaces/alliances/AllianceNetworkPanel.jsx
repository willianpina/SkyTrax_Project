import React, { memo } from "react";
import { useTranslation } from "react-i18next";
import { Network } from "lucide-react";
import { OperationalModuleCard } from "../../components/forecasting/OperationalModuleCard";
import { formatScore } from "../../utils/formatMetric";
import { ALLIANCE_THEME, heatmapCells, sortAlliances } from "./allianceShared";

const DIM_KEYS = ["reputation", "sentiment", "complaints", "risk", "stability"];

function cellSeverity(val, invert = false) {
  const v = invert ? 100 - val : val;
  if (v >= 70) return "good";
  if (v >= 40) return "warn";
  return "crit";
}

function AllianceNetworkPanelInner({ alliances, loading }) {
  const { t } = useTranslation("alliances");
  const sorted = sortAlliances(alliances);
  const isEmpty = !loading && sorted.length === 0;

  const dimLabels = {
    reputation: t("heatmapReputation"),
    sentiment: t("heatmapSentiment"),
    complaints: t("heatmapComplaints"),
    risk: t("heatmapRisk"),
    stability: t("heatmapStability"),
  };

  return (
    <OperationalModuleCard
      className="alliance-network-module"
      title={t("networkTitle")}
      subtitle={t("networkSubtitle")}
      expandable
      defaultExpanded={sorted.length > 0}
      bodyClassName="alliance-network-module__body"
    >
      {loading && isEmpty ? (
        <div className="alliance-module-skeleton" />
      ) : isEmpty ? (
        <div className="alliance-empty-runtime alliance-empty-runtime--compact">
          <Network size={18} strokeWidth={1.2} aria-hidden />
          <p className="alliance-empty-runtime__title">{t("emptyTitle")}</p>
          <p className="alliance-empty-runtime__detail">{t("emptyDetail")}</p>
        </div>
      ) : (
        <div className="alliance-network-heatmap" role="grid" aria-label={t("networkTitle")}>
          <div className="alliance-network-row alliance-network-row--header" role="row">
            <span className="alliance-network-cell alliance-network-cell--name" role="columnheader" />
            {DIM_KEYS.map((key) => (
              <span className="alliance-network-cell" key={key} role="columnheader">
                {dimLabels[key]}
              </span>
            ))}
          </div>
          {sorted.map((a) => {
            const cells = heatmapCells(a);
            const accent = ALLIANCE_THEME[a.name]?.accent || "#94a3b8";
            const values = {
              reputation: cells.reputation,
              sentiment: cells.sentiment,
              complaints: cells.complaints,
              risk: cells.risk,
              stability: cells.stability,
            };
            return (
              <div className="alliance-network-row" key={a.id || a.name} role="row">
                <span
                  className="alliance-network-cell alliance-network-cell--name"
                  role="rowheader"
                  style={{ "--alliance-accent": accent }}
                >
                  <span className="alliance-compare-dot" style={{ background: accent }} aria-hidden />
                  {a.name}
                </span>
                {DIM_KEYS.map((key) => {
                  const val = values[key];
                  const invert = key === "complaints" || key === "risk";
                  const sev = cellSeverity(val, invert);
                  return (
                    <span
                      className={`alliance-network-cell alliance-network-val alliance-network-val--${sev}`}
                      key={key}
                      role="gridcell"
                    >
                      {formatScore(val, { allowZero: true })}
                    </span>
                  );
                })}
              </div>
            );
          })}
        </div>
      )}
    </OperationalModuleCard>
  );
}

export const AllianceNetworkPanel = memo(AllianceNetworkPanelInner);
