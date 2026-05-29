import React, { memo } from "react";

const VARIANT_MAP = {
  danger:  "ob--danger",
  critical:"ob--danger",
  high:    "ob--danger",
  warning: "ob--warning",
  medium:  "ob--warning",
  success: "ob--success",
  positive:"ob--success",
  low:     "ob--success",
  info:    "ob--info",
  neutral: "ob--neutral",
};

function Badge({ children, severity, variant, score, compact, glow, className = "" }) {
  const resolved = variant || severity || "neutral";
  const cls = VARIANT_MAP[resolved] || "ob--neutral";
  const compactCls = compact ? "ob--compact" : "";
  const glowCls = glow ? "ob--glow" : "";

  return (
    <span className={`ob ${cls} ${compactCls} ${glowCls} ${className}`.trim()}>
      {score !== undefined && <span className="ob-score">{score}</span>}
      {children}
    </span>
  );
}

export const OperationalBadge = memo(Badge);
