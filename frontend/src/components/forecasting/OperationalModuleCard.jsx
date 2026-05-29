import React, { memo, useState } from "react";
import { ChevronDown } from "lucide-react";

export const OperationalModuleCard = memo(function OperationalModuleCard({
  title,
  subtitle,
  meta,
  status,
  children,
  className = "",
  bodyClassName = "",
  id,
  expandable = false,
  defaultExpanded = true,
}) {
  const [expanded, setExpanded] = useState(defaultExpanded);

  return (
    <article
      className={`op-module-card ${expandable && !expanded ? "op-module-card--collapsed" : ""} ${className}`.trim()}
      id={id}
    >
      {(title || subtitle || meta || expandable) && (
        <header className="op-module-header">
          <div className="op-module-header-titles">
            {title ? <h2 className="op-module-title">{title}</h2> : null}
            {subtitle ? <p className="op-module-subtitle">{subtitle}</p> : null}
          </div>
          <div className="op-module-meta">
            {meta}
            {expandable ? (
              <button
                type="button"
                className="op-module-expand-btn"
                onClick={() => setExpanded((e) => !e)}
                aria-expanded={expanded}
                aria-label={expanded ? "Collapse" : "Expand"}
              >
                <ChevronDown size={14} className={expanded ? "rotated" : ""} />
              </button>
            ) : null}
          </div>
        </header>
      )}
      {status ? <div className="op-module-status">{status}</div> : null}
      {(!expandable || expanded) && (
        <div className={`op-module-body ${bodyClassName}`.trim()}>{children}</div>
      )}
    </article>
  );
});
