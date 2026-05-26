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
  TrendingDown, TrendingUp, AlertTriangle, Zap, BarChart3,
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

      <PrioritySignals signals={signals} />

      <ReputationTable registry={registry} onAirlineClick={handleAirlineClick} />

      <AirlineDrilldownModal airline={selectedAirline} onClose={handleCloseModal} />
    </WorkspaceShell>
  );
}
