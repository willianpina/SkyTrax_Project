import React, { memo } from "react";

function WorkspaceShellInner({ id, title, subtitle, accent = "signal", actions, children }) {
  return (
    <div className={`workspace-shell workspace-${id}`} data-accent={accent}>
      <header className="workspace-header glass-panel">
        <div className="workspace-header-titles">
          <h1 className="workspace-title">{title}</h1>
          {subtitle && <p className="workspace-subtitle">{subtitle}</p>}
        </div>
        {actions && <div className="workspace-actions">{actions}</div>}
      </header>
      <div className="workspace-content">{children}</div>
    </div>
  );
}

export const WorkspaceShell = memo(WorkspaceShellInner);
