import React, { useMemo, useState, useCallback } from "react";
import { useTranslation } from "react-i18next";
import { useSharedAnalytics } from "../../hooks/AnalyticsProvider";
import { WorkspaceShell } from "../../layouts/WorkspaceShell";
import { PanelShell, TrendArrow } from "../../components/ui/PanelShell";
import { OperationalBadge } from "../../components/ui/OperationalBadge";
import { formatScore, formatDeltaNumeric } from "../../utils/formatMetric";
import {
  buildReputationRegistry,
  computeReputationKPIs,
  extractPrioritySignals,
} from "../../lib/reputationIntelligence";
import { ReputationKpiStrip } from "./ReputationKpiStrip";
import { ReputationTable } from "./ReputationTable";
import { AirlineDrilldownModal } from "./AirlineDrilldownModal";
import {
  TrendingDown, TrendingUp, AlertTriangle, Zap, BarChart3, Radio,
} from "lucide-react";

const SIGNAL_ICONS = {
  worstDeterioration: TrendingDown,
  bestRecovery: TrendingUp,
  criticalRisk: AlertTriangle,
  highComplaints: BarChart3,
  incidentCluster: Zap,
};

const SIGNAL_ACCENTS = {
  worstDeterioration: "risk",
  bestRecovery: "positive",
  criticalRisk: "risk",
  highComplaints: "warning",
  incidentCluster: "risk",
};

function PrioritySignals({ signals }) {
  const { t } = useTranslation(["dashboard"]);
  const keys = Object.keys(signals).filter((k) => signals[k].length > 0);
  if (keys.length === 0) return null;

  return (
    <section className="rep-signals">
      <h3 className="rep-signals-title">{t("dashboard:reputation.signals.title")}</h3>
      <div className="rep-signals-grid">
        {keys.map((key) => {
          const Icon = SIGNAL_ICONS[key] || AlertTriangle;
          const items = signals[key];
          return (
            <div className={`rep-signal-card rep-signal-card--${SIGNAL_ACCENTS[key] || "neutral"}`} key={key}>
              <div className="rep-signal-head">
                <Icon size={13} />
                <span>{t(`dashboard:reputation.signals.${key}`)}</span>
              </div>
              <div className="rep-signal-items">
                {items.map((r) => (
                  <div className="rep-signal-item" key={r.slug}>
                    <span className="rep-signal-name">{r.airline}</span>
                    <span className="rep-signal-val metric-num">
                      {key === "bestRecovery" || key === "worstDeterioration"
                        ? formatDeltaNumeric(r.forecastDelta)
                        : key === "highComplaints"
                          ? formatScore(r.complaints, { allowZero: true })
                          : key === "incidentCluster"
                            ? r.incidents
                            : formatScore(r.score, { allowZero: true })
                      }
                    </span>
                  </div>
                ))}
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}

function LiveIntelFeed({ registry }) {
  const { t } = useTranslation(["dashboard"]);

  const feed = useMemo(() => {
    const items = [];
    for (const r of registry) {
      if (r.risk === "critical" && r.reviewCount >= 5) {
        items.push({ type: "critical", airline: r.airline, slug: r.slug, value: r.score, label: t("dashboard:reputation.feed.critical") });
      }
      if (r.incidents >= 2) {
        items.push({ type: "incident", airline: r.airline, slug: r.slug, value: r.incidents, label: t("dashboard:reputation.feed.incidents") });
      }
      if (r.forecastDelta < -4) {
        items.push({ type: "deterioration", airline: r.airline, slug: r.slug, value: r.forecastDelta, label: t("dashboard:reputation.feed.deterioration") });
      }
      if (r.forecastDelta > 4) {
        items.push({ type: "recovery", airline: r.airline, slug: r.slug, value: r.forecastDelta, label: t("dashboard:reputation.feed.recovery") });
      }
      if (r.complaints > 30) {
        items.push({ type: "complaints", airline: r.airline, slug: r.slug, value: r.complaints, label: t("dashboard:reputation.feed.complaints") });
      }
    }
    return items.slice(0, 12);
  }, [registry, t]);

  if (feed.length === 0) return null;

  const typeIcons = { critical: AlertTriangle, incident: Zap, deterioration: TrendingDown, recovery: TrendingUp, complaints: BarChart3 };
  const typeAccents = { critical: "risk", incident: "risk", deterioration: "risk", recovery: "positive", complaints: "warning" };

  return (
    <section className="rep-live-feed">
      <div className="rep-live-feed-header">
        <Radio size={12} className="rep-live-pulse" />
        <h3>{t("dashboard:reputation.feed.title")}</h3>
      </div>
      <div className="rep-live-feed-items">
        {feed.map((item, i) => {
          const Icon = typeIcons[item.type] || AlertTriangle;
          return (
            <div className={`rep-live-item rep-live-item--${typeAccents[item.type]}`} key={`${item.slug}-${item.type}-${i}`}>
              <Icon size={12} />
              <span className="rep-live-airline">{item.airline}</span>
              <span className="rep-live-label">{item.label}</span>
              <span className="rep-live-value metric-num">
                {item.type === "deterioration" || item.type === "recovery" ? formatDeltaNumeric(item.value) : item.value}
              </span>
            </div>
          );
        })}
      </div>
    </section>
  );
}

export default function ReputationWorkspace() {
  const { t } = useTranslation(["dashboard", "nav", "charts", "common"]);
  const { reputation, benchmarking, anomalies, alerts, forecasts } = useSharedAnalytics();
  const [selectedAirline, setSelectedAirline] = useState(null);

  const registry = useMemo(
    () => buildReputationRegistry(reputation, benchmarking, anomalies, alerts, forecasts),
    [reputation, benchmarking, anomalies, alerts, forecasts]
  );

  const kpis = useMemo(
    () => computeReputationKPIs(registry),
    [registry]
  );

  const signals = useMemo(() => extractPrioritySignals(registry), [registry]);

  const handleAirlineClick = useCallback((row) => setSelectedAirline(row), []);
  const handleCloseModal = useCallback(() => setSelectedAirline(null), []);

  return (
    <WorkspaceShell
      id="reputation"
      title={t("dashboard:reputation.title")}
      subtitle={t("dashboard:reputation.subtitle")}
      accent="positive"
    >
      <ReputationKpiStrip kpis={kpis} />

      <LiveIntelFeed registry={registry} />

      <PrioritySignals signals={signals} />

      <ReputationTable registry={registry} onAirlineClick={handleAirlineClick} />

      <AirlineDrilldownModal airline={selectedAirline} onClose={handleCloseModal} />
    </WorkspaceShell>
  );
}
