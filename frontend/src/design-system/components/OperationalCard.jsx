import React from "react";

export function OperationalCard({ title, subtitle, children, footer, className = "" }) {
  return (
    <section className={`sods-operational-card ${className}`.trim()}>
      {(title || subtitle) ? (
        <header className="sods-operational-card__head">
          {title ? <h4>{title}</h4> : null}
          {subtitle ? <p>{subtitle}</p> : null}
        </header>
      ) : null}
      <div className="sods-operational-card__body">{children}</div>
      {footer ? <footer className="sods-operational-card__foot">{footer}</footer> : null}
    </section>
  );
}
