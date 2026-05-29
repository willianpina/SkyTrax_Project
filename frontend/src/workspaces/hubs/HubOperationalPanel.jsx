import React, { memo } from "react";
import { useTranslation } from "react-i18next";
import { MapPin, Radio } from "lucide-react";
import { OperationalModuleCard } from "../../components/forecasting/OperationalModuleCard";
import { formatScore } from "../../utils/formatMetric";
import {
  resolveDominantCarrier,
  riskTone,
  scoreTone,
  topHubRankings,
} from "./hubsShared";

function HubOperationalPanelInner({ rankings, concentration, loading, onSync, syncing }) {
  const { t } = useTranslation("hubs");
  const rows = topHubRankings(rankings, 10);
  const isEmpty = !loading && rows.length === 0;

  const status = (
    <span className="op-status-pill">
      <Radio size={12} aria-hidden />
      {rows.length ? `Top ${rows.length}` : t("badgeRuntime")}
    </span>
  );

  return (
    <OperationalModuleCard
      className="hub-operational-module"
      title={t("operationalTitle")}
      subtitle={t("operationalSubtitle")}
      status={status}
      expandable
      defaultExpanded
      bodyClassName="hub-operational-module__body"
    >
      {loading && isEmpty ? (
        <div className="hub-module-skeleton" />
      ) : isEmpty ? (
        <div className="hub-empty-runtime hub-empty-runtime--compact">
          <MapPin size={22} strokeWidth={1.2} aria-hidden />
          <p className="hub-empty-runtime__title">{t("emptyHubTitle")}</p>
          <p className="hub-empty-runtime__detail">{t("emptyHubDetail")}</p>
          {onSync ? (
            <button type="button" className="ops-sync-btn" onClick={onSync} disabled={syncing}>
              <Radio size={14} className={syncing ? "pulse-icon" : ""} aria-hidden />
              <span>{syncing ? t("emptySyncing") : t("emptySync")}</span>
            </button>
          ) : null}
        </div>
      ) : (
        <div className="hub-runtime-scroll benchmark-runtime-scroll">
          <div className="hub-runtime-head acm-table--runtime" role="row">
            <span>{t("tableHub")}</span>
            <span>{t("tableCountry")}</span>
            <span>{t("tableDominant")}</span>
            <span>{t("tableScore")}</span>
            <span>{t("tableRisk")}</span>
          </div>
          {rows.map((hub, i) => {
            const dominant = resolveDominantCarrier(hub.iata, concentration);
            const scoreCls = scoreTone(hub.operational_score ?? 0);
            const riskCls = riskTone(hub.risk_score ?? 0);
            return (
              <div
                className={`hub-runtime-row acm-row ${i % 2 === 1 ? "hub-runtime-row--alt" : ""}`}
                key={hub.iata || hub.airport_name}
                role="row"
              >
                <span className="hub-runtime-hub acm-name">
                  <strong>{hub.airport_name}</strong>
                  {hub.iata ? <span className="hub-runtime-iata">{hub.iata}</span> : null}
                </span>
                <span className="hub-runtime-cell acm-cell">{hub.country || "—"}</span>
                <span className="hub-runtime-cell acm-cell hub-runtime-dominant">{dominant}</span>
                <span className="hub-runtime-cell acm-cell">
                  <span className={`hub-score-pill hub-score-pill--${scoreCls}`}>
                    {formatScore(hub.operational_score, { allowZero: true })}
                  </span>
                </span>
                <span className="hub-runtime-cell acm-cell">
                  <span className={`acm-risk-badge acm-risk--${riskCls === "high" ? "critical" : riskCls}`}>
                    {formatScore(hub.risk_score, { allowZero: true })}
                  </span>
                </span>
              </div>
            );
          })}
        </div>
      )}
    </OperationalModuleCard>
  );
}

export const HubOperationalPanel = memo(HubOperationalPanelInner);
