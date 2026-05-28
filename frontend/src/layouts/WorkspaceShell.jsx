import React, { memo } from "react";
import { useTranslation } from "react-i18next";
import { safeT } from "../utils/i18nSafety";

function WorkspaceShellInner({ id, title, subtitle, accent = "signal", actions, children, className = "" }) {
  const { t } = useTranslation("nav");

  const resolvedTitle = title || safeT(t, `modules.${id}.title`, id);
  const resolvedSubtitle = subtitle || safeT(t, `modules.${id}.subtitle`, "");

  return (
    <div className={`workspace-shell workspace-${id} ${className}`.trim()} data-accent={accent}>
      <header className="workspace-header workspace-header--quiet">
        <div className="workspace-header-titles">
          <span className="workspace-micro-label">
            {t("platform.tagline")}
          </span>
          <h1 className="workspace-title">{resolvedTitle}</h1>
          {resolvedSubtitle && <p className="workspace-subtitle">{resolvedSubtitle}</p>}
        </div>
        {actions && <div className="workspace-actions">{actions}</div>}
      </header>
      <div className="workspace-content">{children}</div>
    </div>
  );
}

export const WorkspaceShell = memo(WorkspaceShellInner);
