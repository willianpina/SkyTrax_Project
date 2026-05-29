import React from "react";

export function SectionTitle({ title, subtitle, action }) {
  return (
    <header className="sods-section-title">
      <div>
        <h3>{title}</h3>
        {subtitle ? <p>{subtitle}</p> : null}
      </div>
      {action ? <div className="sods-section-title__action">{action}</div> : null}
    </header>
  );
}
