import React from "react";
import { Activity, X } from "lucide-react";

export function OperationalHeader({
  title,
  subtitle,
  badges,
  status,
  operationId,
  actions,
  onClose,
  icon,
}) {
  const Icon = icon || Activity;
  return (
    <header className="sods-operational-header" title={operationId ? `Operation ${operationId}` : undefined}>
      <div className="sods-operational-header__primary">
        <div className="sods-operational-header__icon"><Icon size={18} /></div>
        <div className="sods-operational-header__copy">
          <h2>{title}</h2>
          {subtitle ? <p>{subtitle}</p> : null}
        </div>
      </div>
      <div className="sods-operational-header__aside">
        <div className="sods-operational-header__badges">{badges}</div>
        <div className="sods-operational-header__tools">
          {status}
          {actions}
          {onClose ? (
            <button type="button" className="sods-icon-btn" onClick={onClose} aria-label="Close panel">
              <X size={15} />
            </button>
          ) : null}
        </div>
      </div>
    </header>
  );
}
