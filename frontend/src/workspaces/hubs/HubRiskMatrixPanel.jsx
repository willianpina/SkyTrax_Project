import React, { memo, useMemo } from "react";
import { useTranslation } from "react-i18next";
import { Shield } from "lucide-react";
import { OperationalModuleCard } from "../../components/forecasting/OperationalModuleCard";
import { RISK_MATRIX_KEYS, riskMatrixRows } from "./hubsShared";

const MATRIX_LABELS = {
  delays: "matrixDelays",
  baggage: "matrixBaggage",
  crew: "matrixService",
  complaints: "matrixComplaints",
};

function HubRiskMatrixPanelInner({ hubRisk, loading }) {
  const { t } = useTranslation("hubs");
  const rows = useMemo(() => riskMatrixRows(hubRisk), [hubRisk]);
  const isEmpty = !loading && rows.length === 0;

  const maxVal = useMemo(() => {
    return Math.max(
      1,
      ...rows.flatMap((r) => [
        r.matrix.delays,
        r.matrix.baggage,
        r.matrix.crew,
        r.matrix.complaints,
      ])
    );
  }, [rows]);

  const cols = [...RISK_MATRIX_KEYS, "complaints"];

  return (
    <OperationalModuleCard
      className="hub-risk-matrix-module"
      title={t("riskMatrixTitle")}
      subtitle={t("riskMatrixSubtitle")}
      expandable
      defaultExpanded={rows.length > 0}
      bodyClassName="hub-risk-matrix-module__body"
    >
      {loading && isEmpty ? (
        <div className="hub-module-skeleton" />
      ) : isEmpty ? (
        <div className="hub-empty-runtime hub-empty-runtime--compact">
          <Shield size={18} strokeWidth={1.2} aria-hidden />
          <p className="hub-empty-runtime__title">{t("emptyHubTitle")}</p>
          <p className="hub-empty-runtime__detail">{t("emptyHubDetail")}</p>
        </div>
      ) : (
        <div className="hub-risk-heatmap" role="grid">
          <div className="hub-risk-row hub-risk-row--header" role="row">
            <span className="hub-risk-cell hub-risk-cell--name" role="columnheader" />
            {cols.map((key) => (
              <span className="hub-risk-cell" key={key} role="columnheader">
                {t(MATRIX_LABELS[key])}
              </span>
            ))}
          </div>
          {rows.map((row) => (
            <div className="hub-risk-row" key={row.iata || row.airport_name} role="row">
              <span className="hub-risk-cell hub-risk-cell--name" role="rowheader">
                {row.iata || row.airport_name?.slice(0, 14)}
              </span>
              {cols.map((key) => {
                const val = row.matrix[key] || 0;
                const intensity = val / maxVal;
                const sev = intensity >= 0.65 ? "crit" : intensity >= 0.35 ? "warn" : "good";
                return (
                  <span
                    className={`hub-risk-cell hub-risk-val hub-risk-val--${sev}`}
                    key={key}
                    role="gridcell"
                    title={`${t(MATRIX_LABELS[key])}: ${val}`}
                  >
                    {val > 0 ? val : "—"}
                  </span>
                );
              })}
            </div>
          ))}
        </div>
      )}
    </OperationalModuleCard>
  );
}

export const HubRiskMatrixPanel = memo(HubRiskMatrixPanelInner);
