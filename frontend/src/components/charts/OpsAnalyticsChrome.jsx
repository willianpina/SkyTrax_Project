import React, { memo } from "react";

export const OpsAnalyticsKpis = memo(function OpsAnalyticsKpis({ items = [] }) {
  if (!items.length) return null;
  return (
    <div className="ops-analytics-kpis" role="list">
      {items.map((item) => (
        <div
          key={item.label}
          className={`ops-kpi-cell ops-kpi-cell--${item.accent || "muted"}`}
          role="listitem"
        >
          <span className="ops-kpi-label">{item.label}</span>
          <span className="ops-kpi-value">{item.value}</span>
          {item.sub ? <span className="ops-kpi-sub">{item.sub}</span> : null}
        </div>
      ))}
    </div>
  );
});

export const OpsChartLegend = memo(function OpsChartLegend({ items = [] }) {
  if (!items.length) return null;
  return (
    <div className="ops-chart-legend" aria-hidden={false}>
      {items.map((item) => (
        <span key={item.label} className="ops-legend-item">
          <span className={`ops-legend-swatch ops-legend-swatch--${item.tone || "muted"}`} />
          {item.label}
        </span>
      ))}
    </div>
  );
});
