import React, { memo, useMemo } from "react";
import { useTranslation } from "react-i18next";
import { TrendingDown } from "lucide-react";
import { OperationalModuleCard } from "../../components/forecasting/OperationalModuleCard";
import { topConcentrationPairs } from "./hubsShared";

function HubConcentrationPanelInner({ concentration, rankings, loading }) {
  const { t } = useTranslation("hubs");
  const pairs = useMemo(
    () => topConcentrationPairs(concentration, rankings, 12),
    [concentration, rankings]
  );
  const isEmpty = !loading && pairs.length === 0;
  const maxRatio = Math.max(0.01, ...pairs.map((p) => p.ratio));

  return (
    <OperationalModuleCard
      className="hub-concentration-module"
      title={t("concentrationTitle")}
      subtitle={t("concentrationSubtitle")}
      expandable
      defaultExpanded={pairs.length > 0}
      bodyClassName="hub-concentration-module__body"
    >
      {loading && isEmpty ? (
        <div className="hub-module-skeleton" />
      ) : isEmpty ? (
        <div className="hub-empty-runtime hub-empty-runtime--compact">
          <TrendingDown size={18} strokeWidth={1.2} aria-hidden />
          <p className="hub-empty-runtime__title">{t("emptyHubTitle")}</p>
          <p className="hub-empty-runtime__detail">{t("emptyHubDetail")}</p>
        </div>
      ) : (
        <ul className="hub-concentration-list" role="list">
          {pairs.map((p) => {
            const pct = (p.ratio / maxRatio) * 100;
            const tone =
              p.exposure === "critical"
                ? "high"
                : p.exposure === "high"
                  ? "medium"
                  : "low";
            return (
              <li className="hub-concentration-row" key={p.id} role="listitem">
                <div className="hub-concentration-row-top">
                  <strong className="hub-concentration-route">
                    {p.hub}
                    <span className="hub-concentration-arrow">→</span>
                    {p.airline}
                  </strong>
                  <span className={`hub-concentration-pct hub-concentration-pct--${tone}`}>
                    {Math.round(p.ratio * 100)}%
                  </span>
                </div>
                <div className="hub-concentration-track" aria-hidden>
                  <div
                    className={`hub-concentration-fill hub-concentration-fill--${tone}`}
                    style={{ width: `${pct}%` }}
                  />
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </OperationalModuleCard>
  );
}

export const HubConcentrationPanel = memo(HubConcentrationPanelInner);
