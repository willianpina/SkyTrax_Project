import React, { memo } from "react";
import { useTranslation } from "react-i18next";
import { X, Shield, TrendingDown, TrendingUp, Minus, AlertTriangle, Star, Globe, Users, Plane, MapPin } from "lucide-react";
import { OperationalBadge } from "../../components/ui/OperationalBadge";
import { formatScore } from "../../utils/formatMetric";

const BREAKDOWN = [
  { key: "sentiment", weight: 25, color: "var(--signal, #38bdf8)" },
  { key: "complaints", weight: 25, color: "var(--warning, #f59e0b)" },
  { key: "negativeFreq", weight: 15, color: "var(--risk, #ef4444)" },
  { key: "trend", weight: 15, color: "var(--positive, #22c55e)" },
  { key: "incidents", weight: 10, color: "var(--text-muted, #64748b)" },
  { key: "opRisk", weight: 10, color: "var(--accent-secondary, #8b5cf6)" },
];

const RISK_VARIANTS = {
  critical: "danger",
  high: "danger",
  attention: "warning",
  stable: "success",
  excellent: "info",
};

function AirlineDrilldownModalInner({ airline, onClose }) {
  const { t } = useTranslation(["dashboard"]);
  if (!airline) return null;

  const TrendIcon = airline.trend === "declining" ? TrendingDown : airline.trend === "improving" ? TrendingUp : Minus;
  const trendColor = airline.trend === "declining" ? "var(--risk)" : airline.trend === "improving" ? "var(--positive)" : "var(--text-muted)";

  return (
    <div className="rep-modal-overlay" onClick={onClose}>
      <div className="rep-modal" onClick={(e) => e.stopPropagation()}>
        <div className="rep-modal-header">
          <div className="rep-modal-title-group">
            <h2>
              {airline.airline}
              {airline.iataCode && <span className="rep-modal-iata">{airline.iataCode}</span>}
            </h2>
            <div className="rep-modal-meta">
              {airline.country !== "—" && <span><Globe size={12} /> {airline.country}</span>}
              {airline.alliance && <span><Users size={12} /> {airline.alliance}</span>}
              {airline.primaryHub && <span><MapPin size={12} /> {airline.primaryHub}</span>}
              {airline.starRating > 0 && <span><Star size={12} /> {airline.starRating}★</span>}
              {airline.icaoCode && <span><Plane size={12} /> {airline.icaoCode}</span>}
            </div>
          </div>
          <button type="button" className="rep-modal-close" onClick={onClose}>
            <X size={18} />
          </button>
        </div>

        <div className="rep-modal-body">
          <div className="rep-modal-score-section">
            <div className={`rep-modal-score rep-score--${airline.risk}`}>
              <span className="rep-modal-score-value metric-num">{formatScore(airline.score, { allowZero: true })}</span>
              <OperationalBadge variant={RISK_VARIANTS[airline.risk] || "neutral"}>
                {t(`dashboard:reputation.risk.${airline.risk}`)}
              </OperationalBadge>
            </div>
            <div className="rep-modal-trend" style={{ color: trendColor }}>
              <TrendIcon size={16} />
              <span>{t(`dashboard:reputation.trend.${airline.trend || "stable"}`)}</span>
            </div>
          </div>

          <div className="rep-modal-breakdown">
            <h3>
              {t("dashboard:reputation.drilldown.scoreBreakdown")}
              <span className="rep-modal-tooltip" title={t("dashboard:reputation.drilldown.tooltipComposition")}>ⓘ</span>
            </h3>
            <div className="rep-breakdown-bar">
              {BREAKDOWN.map(({ key, weight, color }) => (
                <div
                  key={key}
                  className="rep-breakdown-segment"
                  style={{ width: `${weight}%`, backgroundColor: color }}
                  title={`${t(`dashboard:reputation.drilldown.${key}`)} — ${weight}%`}
                />
              ))}
            </div>
            <div className="rep-breakdown-legend">
              {BREAKDOWN.map(({ key, weight, color }) => (
                <div className="rep-breakdown-item" key={key}>
                  <span className="rep-breakdown-dot" style={{ backgroundColor: color }} />
                  <span>{t(`dashboard:reputation.drilldown.${key}`)}</span>
                  <span className="rep-breakdown-pct">{weight}%</span>
                </div>
              ))}
            </div>
          </div>

          <div className="rep-modal-metrics">
            <div className="rep-modal-metric">
              <span className="rep-modal-metric-label">{t("dashboard:reputation.table.complaints")}</span>
              <span className="rep-modal-metric-value metric-num">{formatScore(airline.complaints, { allowZero: true })}</span>
            </div>
            <div className="rep-modal-metric">
              <span className="rep-modal-metric-label">{t("dashboard:reputation.drilldown.operationalRisk")}</span>
              <span className="rep-modal-metric-value metric-num">{airline.operationalRisk || "—"}</span>
            </div>
            <div className="rep-modal-metric">
              <span className="rep-modal-metric-label">{t("dashboard:reputation.table.stability")}</span>
              <span className="rep-modal-metric-value metric-num">{airline.stability}%</span>
            </div>
            <div className="rep-modal-metric">
              <span className="rep-modal-metric-label">{t("dashboard:reputation.table.incidents")}</span>
              <span className="rep-modal-metric-value metric-num">{airline.incidents || "—"}</span>
            </div>
            <div className="rep-modal-metric">
              <span className="rep-modal-metric-label">{t("dashboard:reputation.drilldown.forecastDelta")}</span>
              <span className={`rep-modal-metric-value metric-num ${airline.forecastDelta < 0 ? "delta-neg" : airline.forecastDelta > 0 ? "delta-pos" : ""}`}>
                {airline.forecastDelta > 0 ? "+" : ""}{airline.forecastDelta || "—"}
              </span>
            </div>
            <div className="rep-modal-metric">
              <span className="rep-modal-metric-label">{t("dashboard:reputation.table.reviews")}</span>
              <span className="rep-modal-metric-value metric-num">{airline.reviewCount?.toLocaleString() || "—"}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export const AirlineDrilldownModal = memo(AirlineDrilldownModalInner);
