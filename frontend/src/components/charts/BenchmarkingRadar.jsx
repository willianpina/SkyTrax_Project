import React, { memo, useMemo } from "react";
import { useTranslation } from "react-i18next";
import { baseChartTheme, axisStyle, PALANTIR_COLORS } from "../../lib/chartTheme";
import { LazyEChart } from "../ui/LazyEChart";
import { PanelShell } from "../ui/PanelShell";

function BenchmarkingRadarInner({ radarRows }) {
  const { t, i18n } = useTranslation("charts");
  const rows = (radarRows || []).slice(0, 5);

  const option = useMemo(
    () => ({
      ...baseChartTheme(),
      tooltip: {
        backgroundColor: "rgba(10, 16, 24, 0.94)",
        borderColor: "#2a3d4f",
        textStyle: { color: "#e8eef4" }
      },
      legend: {
        bottom: 0,
        textStyle: { color: PALANTIR_COLORS.muted, fontSize: 10 },
        itemWidth: 12,
        itemHeight: 8
      },
      radar: {
        center: ["50%", "48%"],
        radius: "62%",
        indicator: [
          { name: t("competitiveRadar.rating"), max: 100 },
          { name: t("competitiveRadar.sentiment"), max: 100 },
          { name: t("competitiveRadar.recommend"), max: 100 },
          { name: t("competitiveRadar.lowSeverity"), max: 100 },
          { name: t("competitiveRadar.recency"), max: 100 }
        ],
        axisName: { color: PALANTIR_COLORS.axis, fontSize: 10 },
        splitArea: { areaStyle: { color: ["rgba(30, 42, 54, 0.3)", "rgba(20, 30, 40, 0.2)"] } },
        splitLine: { lineStyle: { color: PALANTIR_COLORS.grid } },
        axisLine: { lineStyle: { color: "#243040" } }
      },
      series: [
        {
          type: "radar",
          symbol: "circle",
          symbolSize: 4,
          lineStyle: { width: 2 },
          areaStyle: { opacity: 0.12 },
          data: rows.map((row, idx) => ({
            name: row.airline,
            value: [
              row.dimensions?.rating ?? 0,
              row.dimensions?.sentiment ?? 0,
              row.dimensions?.recommendation ?? 0,
              row.dimensions?.low_severity ?? 0,
              row.dimensions?.recency ?? 0
            ],
            lineStyle: { color: [PALANTIR_COLORS.signal, PALANTIR_COLORS.positive, PALANTIR_COLORS.warning][idx % 3] },
            itemStyle: { color: [PALANTIR_COLORS.signal, PALANTIR_COLORS.positive, PALANTIR_COLORS.warning][idx % 3] }
          }))
        }
      ]
    }),
    [rows, t, i18n.language]
  );

  return (
    <PanelShell title={t("competitiveRadar.title")} subtitle={t("competitiveRadar.subtitle")} accent="signal">
      <LazyEChart option={option} height={260} />
    </PanelShell>
  );
}

export const BenchmarkingRadar = memo(BenchmarkingRadarInner);
