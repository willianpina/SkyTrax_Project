import React, { memo } from "react";
import { useTranslation } from "react-i18next";
import { TrendingDown, TrendingUp, Minus } from "lucide-react";
import { OperationalModuleCard } from "../../components/forecasting/OperationalModuleCard";
import { ConfidenceBadge } from "../../components/ui/PanelShell";
import { formatScore, formatDeltaNumeric } from "../../utils/formatMetric";

function TopMoversInner({ movers }) {
  const { t } = useTranslation(["charts", "common"]);

  if (!movers.length) return null;

  return (
    <OperationalModuleCard
      className="top-movers-module"
      title={t("charts:topMovers.title", { defaultValue: "Top Movers" })}
      subtitle={t("charts:topMovers.subtitle", { defaultValue: "Largest projected score shifts" })}
      meta={
        <span className="op-module-count">
          {movers.length} {t("charts:table.airlines", { defaultValue: "airlines" })}
        </span>
      }
      bodyClassName="top-movers-module__body"
    >
      <div className="top-movers-rail">
        {movers.map((m) => {
          const declining = m.scoreDelta < 0;
          const improving = m.scoreDelta > 0;
          const Icon = declining ? TrendingDown : improving ? TrendingUp : Minus;
          const accent = declining ? "risk" : improving ? "positive" : "warning";

          return (
            <div key={m.slug} className={`mover-card mover-card--${accent}`}>
              <div className="mover-header">
                <span className="mover-airline">{m.airline}</span>
                <ConfidenceBadge score={m.confidence} insufficient={m.confidence < 30} />
              </div>
              <div className="mover-delta-row">
                <Icon size={14} strokeWidth={2} className={`mover-icon mover-icon--${accent}`} />
                <span className={`mover-delta mover-delta--${accent}`}>
                  {formatDeltaNumeric(m.scoreDelta)}
                </span>
                <span className="mover-range">
                  {formatScore(m.scoreCurrent, { allowZero: true })} → {formatScore(m.scoreForecast, { allowZero: true })}
                </span>
              </div>
              <div className="mover-tags">
                {m.risk !== "low" && (
                  <span className={`ob ob--${m.risk === "critical" ? "danger" : m.risk === "high" ? "danger" : "warning"}`}>
                    {t(`common:severity.${m.risk}`)}
                  </span>
                )}
                {Math.abs(m.complaintDelta) > 3 && (
                  <span className="mover-sub">
                    {t("charts:metrics.complaint_density")}: {formatDeltaNumeric(m.complaintDelta)}
                  </span>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </OperationalModuleCard>
  );
}

export const TopMovers = memo(TopMoversInner);
