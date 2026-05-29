import React from "react";

export function CommandLayout({ header, sidebar, children, className = "" }) {
  return (
    <div className={`sods-command-layout ${className}`.trim()}>
      {sidebar ? <aside className="sods-command-layout__sidebar">{sidebar}</aside> : null}
      <main className="sods-command-layout__main">
        {header}
        <section className="sods-command-layout__content">{children}</section>
      </main>
    </div>
  );
}
