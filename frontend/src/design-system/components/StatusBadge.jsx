import React from "react";
import { AlertTriangle, CheckCircle2, Clock3, Shield, Sparkles } from "lucide-react";

const VARIANT_CLASS = {
  success: "sods-status-badge--success",
  warning: "sods-status-badge--warning",
  active: "sods-status-badge--active",
  degraded: "sods-status-badge--degraded",
  reconciled: "sods-status-badge--reconciled",
  partial: "sods-status-badge--partial",
  "safe-mode": "sods-status-badge--safe",
  "forecast-fallback": "sods-status-badge--fallback",
};

function pickIcon(variant) {
  if (variant === "success" || variant === "reconciled") return CheckCircle2;
  if (variant === "warning" || variant === "partial") return AlertTriangle;
  if (variant === "safe-mode") return Shield;
  if (variant === "forecast-fallback") return Sparkles;
  if (variant === "active") return Clock3;
  return null;
}

export function StatusBadge({
  label,
  variant = "active",
  compact = false,
  pulse = false,
  icon = true,
  className = "",
  title,
}) {
  const Icon = icon ? pickIcon(variant) : null;
  return (
    <span
      className={`sods-status-badge ${VARIANT_CLASS[variant] || ""} ${compact ? "sods-status-badge--compact" : ""} ${className}`.trim()}
      title={title}
    >
      {pulse ? <span className="sods-status-badge__pulse" aria-hidden /> : null}
      {Icon ? <Icon size={11} aria-hidden /> : null}
      <span>{label}</span>
    </span>
  );
}
