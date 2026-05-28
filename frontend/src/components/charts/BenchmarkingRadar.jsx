import React, { memo, useMemo } from "react";
import { useTranslation } from "react-i18next";
import { baseChartTheme, PALANTIR_COLORS } from "../../lib/chartTheme";
import { LazyEChart } from "../ui/LazyEChart";
import { PanelShell } from "../ui/PanelShell";

function BenchmarkingRadarInner({ radarRows, embedded = false }) {
  const { t, i18n } = useTranslation("charts");
  const rows = (radarRows || []).slice(0, 5);

  const option = useMemo(
    () => ({
      ...baseChartTheme({ grid: { left: 12, right: 12, top: 16, bottom: 36 } }),
      tooltip: {
        backgroundColor: "rgba(10, 16, 24, 0.94)",
        borderColor: "#2a3d4f",
        textStyle: { color: "#e8eef4", fontSize: 11 },
      },
      legend: {
        bottom: 0,
        textStyle: { color: PALANTIR_COLORS.muted, fontSize: 9 },
        itemWidth: 10,
        itemHeight: 6,
      },
      radar: {
        center: ["50%", "46%"],
        radius: "58%",
        indicator: [
          { name: t("competitiveRadar.rating"), max: 100 },
          { name: t("competitiveRadar.sentiment"), max: 100 },
          { name: t("competitiveRadar.recommend"), max: 100 },
          { name: t("competitiveRadar.lowSeverity"), max: 100 },
          { name: t("competitiveRadar.recency"), max: 100 },
        ],
        axisName: { color: PALANTIR_COLORS.axis, fontSize: 9 },
        splitArea: { areaStyle: { color: ["rgba(30, 42, 54, 0.25)", "rgba(20, 30, 40, 0.15)"] } },
        splitLine: { lineStyle: { color: "rgba(148, 163, 184, 0.08)" } },
        axisLine: { lineStyle: { color: "rgba(148, 163, 184, 0.12)" } },
      },
      series: [
        {
          type: "radar",
          symbol: "circle",
          symbolSize: 3,
          lineStyle: { width: 1.5 },
          areaStyle: { opacity: 0.08 },
          data: rows.map((row, idx) => ({
            name: row.airline,
            value: [
              row.dimensions?.rating ?? 0,
              row.dimensions?.sentiment ?? 0,
              row.dimensions?.recommendation ?? 0,
              row.dimensions?.low_severity ?? 0,
              row.dimensions?.recency ?? 0,
            ],
            lineStyle: {
              color: [PALANTIR_COLORS.signal, PALANTIR_COLORS.positive, PALANTIR_COLORS.warning][idx % 3],
            },
            itemStyle: {
              color: [PALANTIR_COLORS.signal, PALANTIR_COLORS.positive, PALANTIR_COLORS.warning][idx % 3],
            },
          })),
        },
      ],
    }),
    [rows, t, i18n.language]
  );

  const chart = <LazyEChart option={option} height={240} className="ops-chart-canvas" />;

  if (embedded) {
    return (
      <div className="op-chart-pane">
        <header className="op-chart-pane-header">
          <div className="op-chart-pane-titles">
            <h3 className="op-module-pane-title">{t("competitiveRadar.title")}</h3>
            <p className="op-module-pane-sub">{t("competitiveRadar.subtitle")}</p>
          </div>
        </header>
        <div className="ops-chart-stage ops-chart-stage--flat">{chart}</div>
      </div>
    );
  }

  return (
    <PanelShell title={t("competitiveRadar.title")} subtitle={t("competitiveRadar.subtitle")} accent="signal">
      {chart}
    </PanelShell>
  );
}

export const BenchmarkingRadar = memo(BenchmarkingRadarInner);
