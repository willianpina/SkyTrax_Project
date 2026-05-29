import React from "react";

export function IntelligencePanel({ title, subtitle, children, className = "" }) {
  return (
    <section className={`sods-intelligence-panel ${className}`.trim()}>
      {(title || subtitle) ? (
        <header className="sods-intelligence-panel__head">
          {title ? <h3>{title}</h3> : null}
          {subtitle ? <p>{subtitle}</p> : null}
        </header>
      ) : null}
      <div className="sods-intelligence-panel__body">{children}</div>
    </section>
  );
}
