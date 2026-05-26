import React, { memo, useMemo } from "react";
import { useTranslation } from "react-i18next";
import { baseChartTheme, axisStyle, PALANTIR_COLORS } from "../lib/chartTheme";
import { LazyEChart } from "./ui/LazyEChart";
import { PanelShell, SeverityBadge } from "./ui/PanelShell";
import { formatShortDate } from "../utils/datetime";

function translateAnomalyType(t, type) {
  if (!type) return "";
  return t(`alerts:types.${type}`, { defaultValue: type.replace(/_/g, " ") });
}

export const AnomalyTimeline = memo(function AnomalyTimeline({ anomalies }) {
  const { t, i18n } = useTranslation(["charts", "alerts", "command", "common"]);
  const sorted = [...(anomalies || [])].slice(0, 12).reverse();

  const timelineOption = useMemo(() => {
    const categories = sorted.map((a) => formatShortDate(a.detected_at));
    return {
      ...baseChartTheme({ grid: { left: 48, right: 16, top: 32, bottom: 52 } }),
      xAxis: { type: "category", data: categories, axisLabel: { ...axisStyle().axisLabel, rotate: 28 } },
      yAxis: { type: "value", ...axisStyle() },
      series: [
        {
          type: "bar",
          data: sorted.map((a) => ({
            value: a.observed_value,
            itemStyle: {
              color:
                a.severity === "critical" || a.severity === "high"
                  ? PALANTIR_COLORS.critical
                  : a.severity === "medium"
                    ? PALANTIR_COLORS.warning
                    : PALANTIR_COLORS.signal
            }
          })),
          barWidth: "55%"
        },
        {
          type: "scatter",
          symbol: "pin",
          symbolSize: 22,
          itemStyle: { color: PALANTIR_COLORS.critical, shadowBlur: 8 },
          data: sorted
            .map((a, i) => (a.severity === "high" || a.severity === "critical" ? [i, a.observed_value] : null))
            .filter(Boolean),
          z: 5
        }
      ]
    };
  }, [sorted, i18n.language]);

  return (
    <PanelShell
      title={t("charts:anomalyTimeline.title")}
      subtitle={t("charts:anomalyTimeline.events", { count: (anomalies || []).length })}
      accent="risk"
      expandable
      className="anomaly-timeline-panel"
    >
      {sorted.length === 0 ? (
        <p className="muted-copy">{t("charts:anomalyTimeline.empty")}</p>
      ) : (
        <LazyEChart option={timelineOption} height={200} />
      )}
      <div className="atp-recent">
        {sorted
          .slice(-6)
          .reverse()
          .map((row) => {
            const sev = row.severity || "low";
            const typeName = translateAnomalyType(t, row.anomaly_type);
            return (
              <div className={`atp-row atp-row--${sev}`} key={row.id}>
                <span className={`anm-sev-dot anm-sev-dot--${sev}`} />
                <div className="atp-row-body">
                  <strong className="atp-row-airline">{row.airline}</strong>
                  <span className="atp-row-type">{typeName}</span>
                </div>
                <div className="atp-row-score">
                  <span className="atp-row-obs">{row.observed_value}</span>
                  <span className="atp-row-sep">→</span>
                  <span className="atp-row-exp">{row.expected_value}</span>
                </div>
              </div>
            );
          })}
      </div>
    </PanelShell>
  );
});

export const OperationalAlertsPanel = memo(function OperationalAlertsPanel({ alerts }) {
  const { t } = useTranslation("alerts");

  return (
    <PanelShell
      title={t("operationalAlerts.title")}
      subtitle={t("operationalAlerts.active", { count: (alerts || []).length })}
      accent="risk"
      expandable
    >
      <div className="insight-list tactical">
        {(alerts || []).length === 0 ? (
          <div className="insight-card neutral">
            <p>{t("operationalAlerts.empty")}</p>
          </div>
        ) : (
          alerts.map((alert) => (
            <div className={`insight-card hover-intel severity-${alert.severity}`} key={alert.id}>
              <div className="insight-card-head">
                <SeverityBadge severity={alert.severity} />
                <strong>{alert.title || translateAnomalyType(t, alert.anomaly_type)}</strong>
              </div>
              <p>
                {alert.detail
                  ? t("detail.generic", { airline: alert.airline, detail: alert.detail })
                  : t("detail.observedVsExpected", {
                      airline: alert.airline,
                      observed: alert.observed_value,
                      expected: alert.expected_value,
                      metric: alert.metric || alert.anomaly_type
                    })}
              </p>
            </div>
          ))
        )}
      </div>
    </PanelShell>
  );
});
