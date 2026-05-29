/**
 * Operational metric formatting — intelligence-grade numeric display.
 * Eliminates raw floats, excessive precision, and zero noise.
 */

const intFmt = new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 0 });
const dec1Fmt = new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 1, minimumFractionDigits: 0 });
const pctFmt = new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 0 });

/**
 * Format an executive score (0–100 range).
 * Returns integer or max 1 decimal. Zeros become "—".
 */
export function formatScore(value, { allowZero = false, placeholder = "—" } = {}) {
  if (value == null || (value === 0 && !allowZero)) return placeholder;
  const n = Number(value);
  if (isNaN(n)) return placeholder;
  if (n === 0 && !allowZero) return placeholder;
  const rounded = Math.round(n * 10) / 10;
  if (rounded === Math.round(rounded)) return intFmt.format(Math.round(rounded));
  return dec1Fmt.format(rounded);
}

/**
 * Format a percentage value. Always integer, appends "%".
 * Zero becomes "—".
 */
export function formatPercent(value, { allowZero = false, placeholder = "—" } = {}) {
  if (value == null || (value === 0 && !allowZero)) return placeholder;
  const n = Number(value);
  if (isNaN(n)) return placeholder;
  if (n === 0 && !allowZero) return placeholder;
  return `${pctFmt.format(Math.round(n))}%`;
}

/**
 * Format a delta value with sign. Zero deltas become "Estável" or "—".
 * @param {number} value
 * @param {object} opts
 * @param {string} opts.stableLabel - Label for zero delta (default: "—")
 * @param {number} opts.threshold - Minimum abs value to show (default: 0.5)
 */
export function formatDelta(value, { stableLabel = "—", threshold = 0.5, unit = "" } = {}) {
  if (value == null) return stableLabel;
  const n = Number(value);
  if (isNaN(n) || Math.abs(n) < threshold) return stableLabel;
  const rounded = Math.round(n * 10) / 10;
  const display = rounded === Math.round(rounded)
    ? intFmt.format(Math.abs(Math.round(rounded)))
    : dec1Fmt.format(Math.abs(rounded));
  const sign = rounded > 0 ? "+" : "−";
  return `${sign}${display}${unit}`;
}

/**
 * Format a delta with directional sign, raw numeric (for table cells).
 */
export function formatDeltaNumeric(value, { threshold = 0.5 } = {}) {
  if (value == null) return "—";
  const n = Number(value);
  if (isNaN(n) || Math.abs(n) < threshold) return "—";
  const rounded = Math.round(n * 10) / 10;
  const sign = rounded > 0 ? "+" : "";
  if (rounded === Math.round(rounded)) return `${sign}${Math.round(rounded)}`;
  return `${sign}${rounded.toFixed(1)}`;
}

/**
 * Generic operational metric formatter.
 * Handles score, percent, delta automatically based on type hint.
 */
export function formatMetric(value, type = "score", opts = {}) {
  switch (type) {
    case "percent":
      return formatPercent(value, opts);
    case "delta":
      return formatDelta(value, opts);
    case "deltaNumeric":
      return formatDeltaNumeric(value, opts);
    case "integer":
      return formatScore(value, { ...opts, allowZero: opts.allowZero });
    case "score":
    default:
      return formatScore(value, opts);
  }
}

/**
 * Operational label for score ranges (0–100).
 */
export function scoreLabel(value) {
  const n = Number(value);
  if (isNaN(n) || n == null) return "—";
  if (n <= 0) return "—";
  if (n < 25) return "Critical";
  if (n < 40) return "High Risk";
  if (n < 55) return "Moderate";
  if (n < 70) return "Stable";
  if (n < 85) return "Good";
  return "Excellent";
}

/**
 * Check if a value should be suppressed (is noise).
 */
export function isNoise(value, threshold = 0.5) {
  if (value == null) return true;
  const n = Number(value);
  return isNaN(n) || Math.abs(n) < threshold;
}

/**
 * Format observed → expected display in anomaly panels.
 */
export function formatObservedVsExpected(observed, expected) {
  const obs = formatScore(observed, { allowZero: true });
  const exp = formatScore(expected, { allowZero: true });
  return { obs, exp };
}

/**
 * Format a gap/deviation value.
 */
export function formatGap(observed, expected) {
  const obs = Number(observed);
  const exp = Number(expected);
  if (isNaN(obs) || isNaN(exp)) return null;
  const gap = obs - exp;
  return formatDeltaNumeric(gap, { threshold: 0 });
}
