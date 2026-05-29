import React from "react";
import { Shield } from "lucide-react";
import { KPIStatCard } from "./KPIStatCard";

export function IntegrityPanel({ title = "Integridade operacional", badges, metrics = [], footnote }) {
  return (
    <section className="sods-integrity-panel" aria-label={title}>
      <header className="sods-integrity-panel__head">
        <div className="sods-integrity-panel__title">
          <Shield size={13} />
          <span>{title}</span>
        </div>
        <div className="sods-integrity-panel__badges">{badges}</div>
      </header>
      <div className="sods-integrity-panel__grid">
        {metrics.map((metric) => (
          <KPIStatCard
            key={metric.key}
            value={metric.value}
            label={metric.label}
            hint={metric.hint}
            tone={metric.tone}
          />
        ))}
      </div>
      {footnote ? <p className="sods-integrity-panel__footnote">{footnote}</p> : null}
    </section>
  );
}
