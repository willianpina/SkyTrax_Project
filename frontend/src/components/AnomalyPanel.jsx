import React, { memo, useMemo } from "react";
import { useTranslation } from "react-i18next";
import { baseChartTheme, axisStyle, PALANTIR_COLORS } from "../lib/chartTheme";
import { formatScore } from "../utils/formatMetric";
import { LazyEChart } from "./ui/LazyEChart";
import { PanelShell, SeverityBadge } from "./ui/PanelShell";
import { formatShortDate } from "../utils/datetime";

function translateAnomalyType(t, type) {
  if (!type) return "";
  return t(`alerts:types.${type}`, { defaultValue: type.replace(/_/g, " ") });
}

export const AnomalyTimeline = memo(function AnomalyTimeline({ anomalies, embedded = false }) {
  const { t, i18n } = useTranslation(["charts", "alerts", "command", "common"]);
  const sorted = [...(anomalies || [])].slice(0, 12).reverse();

  const timelineOption = useMemo(() => {
    const categories = sorted.map((a) => formatShortDate(a.detected_at));
    return {
      ...baseChartTheme({ grid: { left: 40, right: 12, top: 16, bottom: 36 } }),
      legend: { show: false },
      xAxis: {
        type: "category",
        data: categories,
        axisLabel: { ...axisStyle().axisLabel, fontSize: 9, rotate: 24 },
        axisTick: { show: false },
      },
      yAxis: {
        type: "value",
        ...axisStyle(),
        splitLine: { lineStyle: { color: "rgba(148, 163, 184, 0.06)" } },
      },
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
                    : PALANTIR_COLORS.signal,
            },
          })),
          barWidth: "50%",
        },
        {
          type: "scatter",
          symbol: "pin",
          symbolSize: 16,
          itemStyle: { color: PALANTIR_COLORS.critical },
          data: sorted
            .map((a, i) =>
              a.severity === "high" || a.severity === "critical" ? [i, a.observed_value] : null
            )
            .filter(Boolean),
          z: 5,
        },
      ],
    };
  }, [sorted, i18n.language]);

  const recentRows = sorted.slice(-5).reverse();

  const body = (
    <>
      {sorted.length === 0 ? (
        <p className="muted-copy ops-empty-state">{t("charts:anomalyTimeline.empty")}</p>
      ) : (
        <div className="ops-chart-stage ops-chart-stage--flat anomaly-timeline-chart">
          <LazyEChart option={timelineOption} height={180} className="ops-chart-canvas" />
        </div>
      )}
      {recentRows.length > 0 ? (
        <div className="atp-recent anomaly-timeline-recent">
          {recentRows.map((row) => {
            const sev = row.severity || "low";
            const typeName = translateAnomalyType(t, row.anomaly_type);
            return (
              <div className={`atp-row atp-row--${sev}`} key={row.id}>
                <span className={`anm-sev-dot anm-sev-dot--${sev}`} aria-hidden />
                <div className="atp-row-body">
                  <strong className="atp-row-airline">{row.airline}</strong>
                  <span className="atp-row-type">{typeName}</span>
                </div>
                <div className="atp-row-score">
                  <span className="atp-row-obs metric-num">
                    {formatScore(row.observed_value, { allowZero: true })}
                  </span>
                  <span className="atp-row-sep">→</span>
                  <span className="atp-row-exp metric-num">
                    {formatScore(row.expected_value, { allowZero: true })}
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      ) : null}
    </>
  );

  if (embedded) {
    return (
      <div className="op-chart-pane anomaly-timeline-embed">
        <header className="op-chart-pane-header">
          <div className="op-chart-pane-titles">
            <h3 className="op-module-pane-title">{t("charts:anomalyTimeline.title")}</h3>
            <p className="op-module-pane-sub">
              {t("charts:anomalyTimeline.events", { count: (anomalies || []).length })}
            </p>
          </div>
        </header>
        {body}
      </div>
    );
  }

  return (
    <PanelShell
      title={t("charts:anomalyTimeline.title")}
      subtitle={t("charts:anomalyTimeline.events", { count: (anomalies || []).length })}
      accent="risk"
      expandable
      className="anomaly-timeline-panel"
    >
      {body}
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
