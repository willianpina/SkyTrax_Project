import React, { memo } from "react";
import { LazyEChart } from "../ui/LazyEChart";
import { PanelShell } from "../ui/PanelShell";

function ChartPanelInner({ title, subtitle, option, height = 240, accent = "signal", badges, emptyMessage, className = "" }) {
  const hasData = option?.series?.some((s) => Array.isArray(s.data) && s.data.length > 0);

  return (
    <PanelShell title={title} subtitle={subtitle} badges={badges} accent={accent} expandable className={className}>
      {!hasData && emptyMessage ? (
        <p className="muted-copy">{emptyMessage}</p>
      ) : (
        <div className="chart-container">
          <LazyEChart option={option} height={height} className="chart-container-canvas" />
        </div>
      )}
    </PanelShell>
  );
}

export const ChartPanel = memo(ChartPanelInner);
