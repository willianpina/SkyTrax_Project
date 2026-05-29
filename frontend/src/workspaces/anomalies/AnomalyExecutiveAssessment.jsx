import React, { memo, useMemo } from "react";
import { useTranslation } from "react-i18next";
import { Brain } from "lucide-react";
import { OperationalModuleCard } from "../../components/forecasting/OperationalModuleCard";
import { SeverityBadge } from "../../components/ui/PanelShell";

function AnomalyExecutiveAssessmentInner({ anomalies }) {
  const { t } = useTranslation(["anomalies"]);

  const insights = useMemo(() => {
    if (!anomalies || anomalies.length === 0) return [];
    const sevCounts = { critical: 0, high: 0, medium: 0, low: 0 };
    const airlineSevs = {};
    for (const a of anomalies) {
      sevCounts[a.severity] = (sevCounts[a.severity] || 0) + 1;
      if (!airlineSevs[a.airline]) airlineSevs[a.airline] = [];
      airlineSevs[a.airline].push(a.severity);
    }

    const msgs = [];
    const criticalAirlines = Object.entries(airlineSevs)
      .filter(([, sevs]) => sevs.includes("critical") || sevs.includes("high"))
      .map(([name]) => name);

    if (criticalAirlines.length > 0) {
      msgs.push({
        sev: "high",
        text: t("assessment.criticalEscalation", {
          count: criticalAirlines.length,
          airlines:
            criticalAirlines.slice(0, 3).join(", ") + (criticalAirlines.length > 3 ? "…" : ""),
        }),
      });
    }
    if (sevCounts.medium > 3) {
      msgs.push({
        sev: "medium",
        text: t("assessment.mediumDetected", { count: sevCounts.medium }),
      });
    }
    if (sevCounts.low > 0) {
      msgs.push({ sev: "low", text: t("assessment.lowTracked", { count: sevCounts.low }) });
    }
    if (msgs.length === 0) {
      msgs.push({ sev: "low", text: t("assessment.allStable") });
    }
    return msgs;
  }, [anomalies, t]);

  return (
    <OperationalModuleCard
      className="anomaly-assessment-module executive-insights-module"
      title={t("assessment.title")}
      subtitle={t("assessment.subtitle")}
      expandable
      defaultExpanded
      status={
        <span className="op-status-pill">
          <Brain size={12} aria-hidden />
          {t("assessment.runtime", { defaultValue: "Strategic posture summary" })}
        </span>
      }
      bodyClassName="anomaly-assessment-module__body"
    >
      <ul className="insight-signal-stream anomaly-assessment-stream" role="list">
        {insights.map((ins, i) => (
          <li
            className={`insight-signal-card anomaly-assess-card severity-${ins.sev}`}
            key={i}
            role="listitem"
          >
            <div className="insight-signal-head">
              <SeverityBadge severity={ins.sev === "high" ? "high" : ins.sev} />
            </div>
            <p className="insight-signal-copy">{ins.text}</p>
          </li>
        ))}
      </ul>
    </OperationalModuleCard>
  );
}

export const AnomalyExecutiveAssessment = memo(AnomalyExecutiveAssessmentInner);
