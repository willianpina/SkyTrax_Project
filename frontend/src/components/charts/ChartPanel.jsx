import React, { memo } from "react";
import { LazyEChart } from "../ui/LazyEChart";
import { PanelShell } from "../ui/PanelShell";

function ChartPanelInner({ title, subtitle, option, height = 240, accent = "signal", badges, emptyMessage }) {
  const hasData = option?.series?.some((s) => Array.isArray(s.data) && s.data.length > 0);

  return (
    <PanelShell title={title} subtitle={subtitle} badges={badges} accent={accent} expandable>
      {!hasData && emptyMessage ? (
        <p className="muted-copy">{emptyMessage}</p>
      ) : (
        <LazyEChart option={option} height={height} />
      )}
    </PanelShell>
  );
}

export const ChartPanel = memo(ChartPanelInner);
