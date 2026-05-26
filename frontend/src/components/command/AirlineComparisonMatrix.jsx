import React, { memo, useMemo } from "react";
import { useTranslation } from "react-i18next";
import { PanelShell } from "../ui/PanelShell";
import { formatScore } from "../../utils/formatMetric";

function AirlineComparisonMatrixInner({ reputation, benchmarking }) {
  const { t } = useTranslation("command");
  const rows = useMemo(() => {
    const rep = (reputation || []).slice(0, 8);
    return rep.map((r) => ({
      slug: r.slug,
      airline: r.airline,
      score: r.score,
      complaint: benchmarking?.complaint_density?.[r.slug] ?? r.complaint_density ?? 0,
      risk: benchmarking?.operational_risk?.[r.slug] ?? 0,
      sentiment: r.sentiment_component ?? 0
    }));
  }, [reputation, benchmarking]);

  const maxScore = Math.max(...rows.map((r) => r.score), 1);

  return (
    <PanelShell
      title={t("matrix.title")}
      subtitle={t("matrix.subtitle")}
      accent="signal"
      className="matrix-panel span-wide"
    >
      <div className="comparison-matrix">
        <div className="matrix-header">
          <span>{t("matrix.airline")}</span>
          <span>{t("matrix.reputation")}</span>
          <span>{t("matrix.complaints")}</span>
          <span>{t("matrix.risk")}</span>
          <span>{t("matrix.sentiment")}</span>
        </div>
        {rows.map((row) => (
          <div className="matrix-row hover-intel" key={row.slug}>
            <span className="matrix-airline">{row.airline}</span>
            <div className="matrix-cell">
              <div className="matrix-bar positive" style={{ width: `${(row.score / maxScore) * 100}%` }} />
              <span className="metric-num">{formatScore(row.score, { allowZero: true })}</span>
            </div>
            <div className="matrix-cell">
              <div className="matrix-bar risk" style={{ width: `${Math.min(100, row.complaint)}%` }} />
              <span className="metric-num">{formatScore(row.complaint, { allowZero: false })}</span>
            </div>
            <div className="matrix-cell">
              <span className={`metric-num ${row.risk > 50 ? "risk-high" : "risk-low"}`}>{formatScore(row.risk, { allowZero: false })}</span>
            </div>
            <div className="matrix-cell">
              <span className="metric-num">{formatScore(row.sentiment, { allowZero: false })}</span>
            </div>
          </div>
        ))}
      </div>
    </PanelShell>
  );
}

export const AirlineComparisonMatrix = memo(AirlineComparisonMatrixInner);
