import React, { memo, useState } from "react";
import { useTranslation } from "react-i18next";
import { ChevronDown } from "lucide-react";

function PanelShellInner({
  title,
  subtitle,
  badges,
  children,
  className = "",
  expandable = false,
  defaultExpanded = true,
  footer,
  accent = "signal",
  quiet = false,
}) {
  const [expanded, setExpanded] = useState(defaultExpanded);
  const quietClass = quiet ? "intel-panel--quiet panel-quiet glass-panel--quiet" : "glass-panel";
  const accentClass = quiet ? "" : `accent-${accent}`;

  return (
    <article className={`intel-panel ${quietClass} ${accentClass} ${className} ${expanded ? "" : "collapsed"}`}>
      <header className="intel-panel-header">
        <div className="intel-panel-titles">
          <h2>{title}</h2>
          {subtitle ? <span className="intel-panel-sub">{subtitle}</span> : null}
        </div>
        <div className="intel-panel-meta">
          {badges}
          {expandable ? (
            <button
              type="button"
              className="panel-expand-btn"
              onClick={() => setExpanded((e) => !e)}
              aria-expanded={expanded}
            >
              <ChevronDown size={14} className={expanded ? "rotated" : ""} />
            </button>
          ) : null}
        </div>
      </header>
      {(!expandable || expanded) && <div className="intel-panel-body fade-in">{children}</div>}
      {footer && expanded ? <footer className="intel-panel-footer">{footer}</footer> : null}
    </article>
  );
}

export const PanelShell = memo(PanelShellInner);

export function SeverityBadge({ severity, label }) {
  const { t } = useTranslation("common");
  const s = (severity || "neutral").toLowerCase();
  const display = label || t(`severity.${s}`, { defaultValue: s });
  return (
    <span className={`ob ob--${s === "critical" || s === "high" ? "danger" : s === "medium" ? "warning" : s === "low" || s === "positive" ? "success" : "neutral"}`} title={display}>
      {display}
    </span>
  );
}

export function ConfidenceBadge({ score, insufficient, label }) {
  const { t } = useTranslation("common");
  if (insufficient) {
    return <span className="ob ob--warning">{label || t("severity.low", { defaultValue: "Low" })}</span>;
  }
  const variant = score >= 75 ? "ob--success" : score >= 45 ? "ob--info" : "ob--warning";
  return (
    <span className={`ob ${variant}`}>
      <span className="ob-score">{label || `${score}%`}</span>
    </span>
  );
}

export function TrendArrow({ direction }) {
  const d = (direction || "stable").toLowerCase();
  const symbol = d === "up" || d === "improving" ? "↑" : d === "down" || d === "declining" ? "↓" : "→";
  return <span className={`trend-arrow trend-${d}`}>{symbol}</span>;
}

export function OperationalTag({ children }) {
  return <span className="op-tag">{children}</span>;
}

export function FallbackPanel({ title, message, onRetry }) {
  const { t } = useTranslation("common");
  return (
    <div className="fallback-panel">
      <strong>{title}</strong>
      <p>{message}</p>
      {onRetry ? (
        <button type="button" className="tactical-btn" onClick={onRetry}>
          {t("actions.retry")}
        </button>
      ) : null}
    </div>
  );
}
