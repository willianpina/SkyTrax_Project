import React from "react";

export function KPIStatCard({ value, label, hint, tone = "default", className = "" }) {
  return (
    <article className={`sods-kpi-card sods-kpi-card--${tone} ${className}`.trim()} title={hint}>
      <strong className="sods-kpi-card__value sods-tabular">{value}</strong>
      <span className="sods-kpi-card__label">{label}</span>
    </article>
  );
}
