import React, { memo } from "react";
import { TrendArrow } from "./ui/PanelShell";

function MetricCardInner({ icon: Icon, label, value, detail, tone = "signal", trend }) {
  return (
    <section className={`tactical-metric hover-intel tone-${tone}`}>
      <div className={`metric-icon ${tone}`}>
        <Icon size={18} strokeWidth={1.75} />
      </div>
      <div className="tactical-metric-body">
        <p className="metric-label">{label}</p>
        <div className="metric-value-row">
          <p className="metric-value">{value}</p>
          {trend ? <TrendArrow direction={trend} /> : null}
        </div>
        <p className="metric-detail">{detail}</p>
      </div>
      <span className="metric-pulse" aria-hidden />
    </section>
  );
}

export const MetricCard = memo(MetricCardInner);
