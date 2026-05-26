import i18n from "i18next";
import LanguageDetector from "i18next-browser-languagedetector";
import { initReactI18next } from "react-i18next";

/** Active locales. Extend with es, fr, de by adding locale folders + loaders. */
export const SUPPORTED_LANGUAGES = ["en", "pt"] as const;
export type AppLanguage = (typeof SUPPORTED_LANGUAGES)[number];

function normalizeLanguage(language?: string | null): AppLanguage {
  if (!language) return "en";
  return language.startsWith("pt") ? "pt" : "en";
}

export const NAMESPACES = ["common", "dashboard", "charts", "alerts", "semantic", "benchmarking", "command", "nav", "aviation", "coverage", "alliances", "hubs", "anomalies"] as const;

const STORAGE_KEY = "skytrax-language";

const localeLoaders: Record<AppLanguage, Record<string, () => Promise<{ default: Record<string, unknown> }>>> = {
  en: {
    common: () => import("./en/common.json"),
    dashboard: () => import("./en/dashboard.json"),
    charts: () => import("./en/charts.json"),
    alerts: () => import("./en/alerts.json"),
    semantic: () => import("./en/semantic.json"),
    benchmarking: () => import("./en/benchmarking.json"),
    command: () => import("./en/command.json"),
    nav: () => import("./en/nav.json"),
    aviation: () => import("./en/aviation.json"),
    coverage: () => import("./en/coverage.json"),
    alliances: () => import("./en/alliances.json"),
    hubs: () => import("./en/hubs.json"),
    anomalies: () => import("./en/anomalies.json")
  },
  pt: {
    common: () => import("./pt/common.json"),
    dashboard: () => import("./pt/dashboard.json"),
    charts: () => import("./pt/charts.json"),
    alerts: () => import("./pt/alerts.json"),
    semantic: () => import("./pt/semantic.json"),
    benchmarking: () => import("./pt/benchmarking.json"),
    command: () => import("./pt/command.json"),
    nav: () => import("./pt/nav.json"),
    aviation: () => import("./pt/aviation.json"),
    coverage: () => import("./pt/coverage.json"),
    alliances: () => import("./pt/alliances.json"),
    hubs: () => import("./pt/hubs.json"),
    anomalies: () => import("./pt/anomalies.json")
  }
};

const loadedLanguages = new Set<string>();

async function loadLanguageBundles(language: AppLanguage) {
  if (loadedLanguages.has(language)) {
    return;
  }
  const loaders = localeLoaders[language];
  await Promise.all(
    NAMESPACES.map(async (namespace) => {
      const module = await loaders[namespace]();
      i18n.addResourceBundle(language, namespace, module.default, true, true);
    })
  );
  loadedLanguages.add(language);
}

export async function initI18n() {
  if (i18n.isInitialized) {
    return i18n;
  }

  const detector = new LanguageDetector();
  detector.addDetector({
    name: "skytraxStorage",
    lookup() {
      return localStorage.getItem(STORAGE_KEY) ?? undefined;
    },
    cacheUserLanguage(lng) {
      localStorage.setItem(STORAGE_KEY, lng);
    }
  });

  const stored = localStorage.getItem(STORAGE_KEY);
  const initialLanguage = stored
    ? normalizeLanguage(stored)
    : normalizeLanguage(typeof navigator !== "undefined" ? navigator.language : "en");

  const isDev = process.env.NODE_ENV === "development";

  await i18n
    .use(detector)
    .use(initReactI18next)
    .init({
      lng: initialLanguage,
      fallbackLng: "en",
      supportedLngs: [...SUPPORTED_LANGUAGES],
      load: "languageOnly",
      nonExplicitSupportedLngs: true,
      ns: [...NAMESPACES],
      defaultNS: "dashboard",
      fallbackNS: "common",
      interpolation: { escapeValue: false },
      detection: {
        order: ["skytraxStorage", "navigator"],
        caches: ["skytraxStorage"]
      },
      react: { useSuspense: false },
      saveMissing: isDev,
      missingKeyHandler: isDev
        ? (_lngs: readonly string[], ns: string, key: string) => {
            console.warn(`[I18N] missing key: ${ns}:${key}`);
          }
        : false,
    });

  document.documentElement.lang = i18n.language === "pt" ? "pt-BR" : "en";

  await loadLanguageBundles("en");
  if (initialLanguage !== "en") {
    await loadLanguageBundles(initialLanguage);
  }

  return i18n;
}

export async function changeAppLanguage(language: string) {
  const normalized = normalizeLanguage(language);
  await loadLanguageBundles(normalized);
  await i18n.changeLanguage(normalized);
  localStorage.setItem(STORAGE_KEY, normalized);
  document.documentElement.lang = normalized === "pt" ? "pt-BR" : "en";
}

export default i18n;
