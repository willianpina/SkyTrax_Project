import React, { useState, useMemo } from "react";
import { useTranslation } from "react-i18next";
import { FileSearch } from "lucide-react";
import { useSharedAnalytics } from "../../hooks/AnalyticsProvider";
import { forecastConfidence } from "../../lib/executiveMetrics";
import { formatScore } from "../../utils/formatMetric";
import { WorkspaceShell } from "../../layouts/WorkspaceShell";
import { SemanticInvestigationPanel } from "../../components/command/SemanticInvestigationPanel";
import { PanelShell, SeverityBadge, ConfidenceBadge, TrendArrow } from "../../components/ui/PanelShell";
import { formatShortDate } from "../../utils/datetime";

export default function InvestigationsWorkspace() {
  const { t } = useTranslation(["command", "alerts", "charts", "nav", "semantic", "dashboard"]);
  const { reputation, benchmarking, anomalies, forecasts, clusters, insights, apiBase } = useSharedAnalytics();

  const [selectedAirline, setSelectedAirline] = useState("");
  const airlines = (reputation || []).map((r) => ({ slug: r.slug, name: r.airline }));

  const filteredAnomalies = useMemo(
    () => selectedAirline ? (anomalies || []).filter((a) => a.airline_slug === selectedAirline || a.airline === selectedAirline) : anomalies || [],
    [anomalies, selectedAirline]
  );

  const airlineRep = useMemo(
    () => selectedAirline ? reputation.find((r) => r.slug === selectedAirline) : null,
    [reputation, selectedAirline]
  );

  const repForecast = (forecasts?.metrics?.reputation_score || []).find((r) => r.horizon === "weekly");
  const conf = forecastConfidence(repForecast);

  return (
    <WorkspaceShell id="investigations" accent="warning">
      <div className="investigation-toolbar glass-panel">
        <FileSearch size={16} />
        <select value={selectedAirline} onChange={(e) => setSelectedAirline(e.target.value)} className="investigation-select">
          <option value="">{t("command:semantic.allAirlines")}</option>
          {airlines.map((a) => (
            <option key={a.slug} value={a.slug}>{a.name}</option>
          ))}
        </select>
      </div>

      {airlineRep && (
        <section className="workspace-kpi-strip">
          <div className="strip-metric severity-low">
            <span className="strip-label">ARS</span>
            <span className="strip-value metric-num">{formatScore(airlineRep.score, { allowZero: true })}</span>
          </div>
          <div className="strip-metric severity-medium">
            <span className="strip-label">{t("command:metrics.complaintDensity")}</span>
            <span className="strip-value metric-num">{formatScore(benchmarking?.complaint_density?.[selectedAirline])}</span>
          </div>
          <div className="strip-metric severity-low">
            <span className="strip-label">{t("command:metrics.operationalRisk")}</span>
            <span className="strip-value metric-num">{formatScore(benchmarking?.operational_risk?.[selectedAirline])}</span>
          </div>
        </section>
      )}

      <div className="command-body">
        <div className="command-central">
          <PanelShell title={t("alerts:incidents.title", { defaultValue: "Anomalies" })} subtitle={`${filteredAnomalies.length} detected`} accent="risk" expandable>
            <div className="incident-list tactical">
              {filteredAnomalies.slice(0, 10).map((a) => (
                <div className={`incident-row hover-intel severity-${a.severity}`} key={a.id}>
                  <SeverityBadge severity={a.severity} label={a.anomaly_type?.replace(/_/g, " ")} />
                  <strong>{a.airline}</strong>
                  <span className="incident-metric">{a.metric}: {a.observed_value} vs {a.expected_value}</span>
                  <time>{formatShortDate(a.detected_at)}</time>
                </div>
              ))}
              {filteredAnomalies.length === 0 && <p className="muted-copy">{t("alerts:operationalAlerts.empty")}</p>}
            </div>
          </PanelShell>

          <PanelShell title={t("charts:reputationForecast.title")} subtitle={t("charts:reputationForecast.subtitle")} accent="warning" badges={<ConfidenceBadge score={conf.score} insufficient={conf.insufficient} />}>
            {repForecast ? (
              <div className="forecast-detail-card">
                <span className="metric-num">{formatScore(repForecast.current_value)} → {formatScore(repForecast.forecast_value)}</span>
                <TrendArrow direction={repForecast.trend_direction} />
              </div>
            ) : (
              <p className="muted-copy">{t("charts:reputationForecast.empty")}</p>
            )}
          </PanelShell>

          <SemanticInvestigationPanel clusters={clusters} apiBase={apiBase} reputation={reputation} />
        </div>

        <aside className="command-rail-right">
          <PanelShell title={t("nav:investigations.insights", { defaultValue: "Related insights" })} accent="warning" expandable>
            <div className="insight-list tactical">
              {(insights || []).slice(0, 5).map((ins) => (
                <div className="insight-card hover-intel" key={ins.id || ins.summary}>
                  <SeverityBadge severity={ins.severity} />
                  <strong>{ins.airline}</strong>
                  <p>{(ins.summary || ins.insight_text || "").slice(0, 100)}</p>
                </div>
              ))}
              {(!insights || insights.length === 0) && <p className="muted-copy">{t("dashboard:insights.noInsights")}</p>}
            </div>
          </PanelShell>
        </aside>
      </div>
    </WorkspaceShell>
  );
}
