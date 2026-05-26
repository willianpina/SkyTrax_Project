import React, { memo, useMemo } from "react";
import { useTranslation } from "react-i18next";
import { baseChartTheme, axisStyle, PALANTIR_COLORS } from "../lib/chartTheme";
import { forecastConfidence } from "../lib/executiveMetrics";
import { formatScore, formatDeltaNumeric } from "../utils/formatMetric";
import { LazyEChart } from "./ui/LazyEChart";
import { ConfidenceBadge, OperationalTag, PanelShell, TrendArrow } from "./ui/PanelShell";

function ForecastPanelInner({ forecasts }) {
  const { t, i18n } = useTranslation(["charts", "common", "command"]);
  const arsRows = (forecasts?.metrics?.reputation_score || []).filter((r) => r.horizon === "weekly");
  const primary = arsRows[0];
  const conf = forecastConfidence(primary);

  const option = useMemo(() => {
    const history = primary?.payload?.history || [];
    const projected = primary?.payload?.forecast_points || [];
    const categories = [...history.map((h) => h.period), ...projected.map((p) => p.period)];
    const actualLabel = t("charts:reputationForecast.actual");
    const forecastLabel = t("charts:reputationForecast.forecast");
    const values = projected.map((p) => p.value).filter((v) => v != null);
    const band = values.length
      ? values.map((v) => [Math.max(0, v - 6), Math.min(100, v + 6)])
      : [];

    return {
      ...baseChartTheme({ grid: { left: 52, right: 24, top: 44, bottom: 48 } }),
      legend: { data: [actualLabel, forecastLabel], top: 4, textStyle: { color: PALANTIR_COLORS.muted, fontSize: 10 } },
      xAxis: { type: "category", data: categories, ...axisStyle() },
      yAxis: { type: "value", min: 0, max: 100, ...axisStyle() },
      series: [
        ...(band.length
          ? [
              {
                name: "CI lower",
                type: "line",
                data: [...history.map(() => null), ...band.map((b) => b[0])],
                lineStyle: { opacity: 0 },
                stack: "band",
                symbol: "none",
                areaStyle: { color: "rgba(61, 158, 255, 0.08)" }
              },
              {
                name: "CI upper",
                type: "line",
                data: [...history.map(() => null), ...band.map((b) => b[1] - b[0])],
                lineStyle: { opacity: 0 },
                stack: "band",
                symbol: "none",
                areaStyle: { color: "rgba(61, 158, 255, 0.08)" }
              }
            ]
          : []),
        {
          name: actualLabel,
          type: "line",
          data: [...history.map((h) => h.value), ...projected.map(() => null)],
          smooth: true,
          lineStyle: { color: PALANTIR_COLORS.positive, width: 2 },
          itemStyle: { color: PALANTIR_COLORS.positive },
          markPoint: conf.insufficient
            ? undefined
            : {
                symbol: "circle",
                symbolSize: 6,
                data: [{ coord: [categories[history.length - 1], history[history.length - 1]?.value] }]
              }
        },
        {
          name: forecastLabel,
          type: "line",
          data: [...history.map(() => null), ...projected.map((p) => p.value)],
          smooth: true,
          lineStyle: { color: PALANTIR_COLORS.warning, width: 2, type: "dashed" }
        }
      ]
    };
  }, [primary, t, i18n.language, conf.insufficient]);

  const badges = (
    <>
      <ConfidenceBadge score={conf.score} insufficient={conf.insufficient} label={t("command:forecast.confidence", { score: conf.score })} />
      <OperationalTag>{conf.method}</OperationalTag>
      {primary?.trend_direction ? <TrendArrow direction={primary.trend_direction} /> : null}
    </>
  );

  return (
    <PanelShell
      title={t("charts:reputationForecast.title")}
      subtitle={t("charts:reputationForecast.subtitle")}
      badges={badges}
      accent="warning"
      className="forecast-panel"
    >
      {arsRows.length === 0 || conf.insufficient ? (
        <p className="muted-copy">{t("charts:reputationForecast.empty")}</p>
      ) : (
        <LazyEChart option={option} height={240} />
      )}
      <div className="forecast-metrics tactical">
        {["sentiment", "complaint_density"].map((metric) => {
          const row = (forecasts?.metrics?.[metric] || []).find((r) => r.horizon === "weekly");
          if (!row) return null;
          const fc = forecastConfidence(row);
          const current = formatScore(row.current_value);
          const forecast = formatScore(row.forecast_value);
          const delta = formatDeltaNumeric(
            row.forecast_value != null && row.current_value != null
              ? row.forecast_value - row.current_value
              : null
          );
          const trendKey = row.trend_direction?.toLowerCase();
          const trendLabel = trendKey ? t(`common:trend.${trendKey}`, { defaultValue: row.trend_direction }) : row.trend_direction;
          return (
            <div className="forecast-chip hover-intel" key={metric}>
              <div className="chip-head">
                <strong>{t(`charts:metrics.${metric}`, { defaultValue: metric.replace("_", " ") })}</strong>
                <ConfidenceBadge score={fc.score} insufficient={fc.insufficient} />
              </div>
              <span className="metric-num">
                {current} → {forecast}
                {delta !== "—" && <small className={delta.startsWith("+") ? "delta-pos" : "delta-neg"}> ({delta})</small>}
              </span>
              <small>
                <TrendArrow direction={row.trend_direction} /> {trendLabel}
              </small>
            </div>
          );
        })}
      </div>
    </PanelShell>
  );
}

export const ForecastPanel = memo(ForecastPanelInner);
