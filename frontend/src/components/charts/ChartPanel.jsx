import React, { memo } from "react";
import { LazyEChart } from "../ui/LazyEChart";
import { PanelShell } from "../ui/PanelShell";
import { OpsAnalyticsKpis, OpsChartLegend } from "./OpsAnalyticsChrome";

function ExecutiveChartBody({
  title,
  subtitle,
  option,
  height = 220,
  badges,
  emptyMessage,
  kpis = [],
  legend = [],
}) {
  const hasData = option?.series?.some((s) => Array.isArray(s.data) && s.data.length > 0);

  return (
    <div className="op-chart-pane">
      {(title || subtitle || badges) && (
        <header className="op-chart-pane-header">
          <div className="op-chart-pane-titles">
            {title ? <h3 className="op-module-pane-title">{title}</h3> : null}
            {subtitle ? <p className="op-module-pane-sub">{subtitle}</p> : null}
          </div>
          {badges ? <div className="op-chart-pane-meta">{badges}</div> : null}
        </header>
      )}

      {kpis.length > 0 ? <OpsAnalyticsKpis items={kpis} /> : null}

      <div className="ops-chart-stage">
        {!hasData && emptyMessage ? (
          <p className="muted-copy ops-empty-state">{emptyMessage}</p>
        ) : (
          <LazyEChart option={option} height={height} className="ops-chart-canvas" />
        )}
      </div>

      {legend.length > 0 && hasData ? <OpsChartLegend items={legend} /> : null}
    </div>
  );
}

function ChartPanelInner({
  title,
  subtitle,
  option,
  height = 220,
  accent = "signal",
  badges,
  emptyMessage,
  className = "",
  variant = "default",
  kpis = [],
  legend = [],
  expandable = false,
  embedded = false,
}) {
  const executive = variant === "executive";
  const hasData = option?.series?.some((s) => Array.isArray(s.data) && s.data.length > 0);

  if (embedded && executive) {
    return (
      <ExecutiveChartBody
        title={title}
        subtitle={subtitle}
        option={option}
        height={height}
        badges={badges}
        emptyMessage={emptyMessage}
        kpis={kpis}
        legend={legend}
      />
    );
  }

  const panelClass = [
    className,
    executive ? "ops-analytics-panel" : "",
    executive ? "chart-panel--executive" : "",
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <PanelShell
      title={title}
      subtitle={subtitle}
      badges={badges}
      accent={accent}
      expandable={expandable || executive}
      defaultExpanded
      className={panelClass}
    >
      {executive ? (
        <ExecutiveChartBody
          option={option}
          height={height}
          emptyMessage={emptyMessage}
          kpis={kpis}
          legend={legend}
        />
      ) : (
        <div className="chart-container">
          {!hasData && emptyMessage ? (
            <p className="muted-copy">{emptyMessage}</p>
          ) : (
            <LazyEChart option={option} height={height} className="chart-container-canvas" />
          )}
        </div>
      )}
    </PanelShell>
  );
}

export const ChartPanel = memo(ChartPanelInner);
