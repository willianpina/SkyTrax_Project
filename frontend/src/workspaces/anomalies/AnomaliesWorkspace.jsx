import React, { useMemo } from "react";
import { useTranslation } from "react-i18next";
import { useSharedAnalytics } from "../../hooks/AnalyticsProvider";
import { WorkspaceShell } from "../../layouts/WorkspaceShell";
import { AnomalyTimeline, OperationalAlertsPanel } from "../../components/AnomalyPanel";
import { AnomalyFeed } from "../../components/command/AnomalyFeed";
import { PanelShell, SeverityBadge } from "../../components/ui/PanelShell";

export default function AnomaliesWorkspace() {
  const { t } = useTranslation(["alerts", "command", "common", "nav"]);
  const { anomalies, alerts } = useSharedAnalytics();

  const severityMatrix = useMemo(() => {
    const counts = { critical: 0, high: 0, medium: 0, low: 0 };
    for (const a of anomalies || []) counts[a.severity] = (counts[a.severity] || 0) + 1;
    for (const a of alerts || []) counts[a.severity] = (counts[a.severity] || 0) + 1;
    return Object.entries(counts).filter(([, v]) => v > 0);
  }, [anomalies, alerts]);

  const totalSignals = (anomalies?.length || 0) + (alerts?.length || 0);

  return (
    <WorkspaceShell id="anomalies" title={t("nav:nav.anomalies")} subtitle={t("alerts:operationalAlerts.active", { count: totalSignals })} accent="risk">
      <section className="workspace-kpi-strip severity-strip">
        {severityMatrix.map(([sev, count]) => (
          <div className={`severity-kpi glass-panel severity-${sev}`} key={sev}>
            <SeverityBadge severity={sev} />
            <span className="severity-count">{count}</span>
          </div>
        ))}
      </section>

      <div className="command-body">
        <div className="command-central">
          <AnomalyTimeline anomalies={anomalies} />
          <OperationalAlertsPanel alerts={alerts} />

          <PanelShell
            title={t("alerts:incidents.title", { defaultValue: "Active incidents" })}
            subtitle={t("alerts:incidents.subtitle", { defaultValue: "All detected anomalies" })}
            accent="risk"
            expandable
          >
            <div className="incident-list tactical">
              {(anomalies || []).map((a) => (
                <div className={`incident-row hover-intel severity-${a.severity}`} key={a.id}>
                  <SeverityBadge severity={a.severity} label={a.anomaly_type?.replace(/_/g, " ")} />
                  <strong>{a.airline}</strong>
                  <span className="incident-metric">{a.metric}: {a.observed_value} vs {a.expected_value}</span>
                  <time>{a.detected_at?.slice(0, 10)}</time>
                </div>
              ))}
              {(!anomalies || anomalies.length === 0) && <p className="muted-copy">{t("alerts:operationalAlerts.empty")}</p>}
            </div>
          </PanelShell>
        </div>
        <aside className="command-rail-right">
          <AnomalyFeed anomalies={anomalies} alerts={alerts} />
        </aside>
      </div>
    </WorkspaceShell>
  );
}
