import React from "react";

export function ExecutiveWorkspace({ title, subtitle, toolbar, children }) {
  return (
    <section className="sods-executive-workspace">
      <header className="sods-executive-workspace__head">
        <div>
          <h1>{title}</h1>
          {subtitle ? <p>{subtitle}</p> : null}
        </div>
        {toolbar ? <div className="sods-executive-workspace__toolbar">{toolbar}</div> : null}
      </header>
      <div className="sods-executive-workspace__body">{children}</div>
    </section>
  );
}
