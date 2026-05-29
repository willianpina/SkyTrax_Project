const UNRESOLVED_PATTERNS = /^(nav\.|modules\.|groups\.|platform\.|.*\.title$|.*\.subtitle$)/;

/**
 * Wraps i18next's t() to prevent raw translation keys from leaking into the UI.
 * Returns fallback text when a key is unresolved instead of exposing internal paths.
 */
export function safeT(t, key, fallbackOrOptions, options) {
  const fallback = typeof fallbackOrOptions === "string" ? fallbackOrOptions : undefined;
  const opts = typeof fallbackOrOptions === "object" ? fallbackOrOptions : options;
  const result = t(key, opts);

  if (typeof result === "string" && UNRESOLVED_PATTERNS.test(result)) {
    if (process.env.NODE_ENV === "development") {
      console.warn(`[I18N] unresolved translation: "${key}" → "${result}"`);
    }
    return fallback || key.split(".").pop().replace(/([A-Z])/g, " $1").trim();
  }
  return result;
}

const MODULE_IDS = [
  "executive", "reputation", "forecasting", "benchmarking",
  "anomalies", "semantic", "aviation", "hubs",
  "alliances", "coverage", "geospatial", "investigations",
];

/**
 * Resolves a module's display labels from the centralized nav:modules.* config.
 * Returns { title, subtitle, shortTitle } with guaranteed non-key values.
 */
export function resolveModuleLabel(t, moduleId) {
  const titleKey = `modules.${moduleId}.title`;
  const subtitleKey = `modules.${moduleId}.subtitle`;

  const title = safeT(t, titleKey, moduleId);
  const subtitle = safeT(t, subtitleKey, "");
  const shortTitle = title.split(" ").slice(-1)[0];

  return { title, subtitle, shortTitle };
}

/**
 * Hook-friendly batch resolver: returns a map of all module labels.
 */
export function resolveAllModuleLabels(t) {
  const labels = {};
  for (const id of MODULE_IDS) {
    labels[id] = resolveModuleLabel(t, id);
  }
  return labels;
}
