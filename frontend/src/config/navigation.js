/**
 * SkyTrax Analytics Platform — Centralized Navigation & Module Registry
 *
 * Single source of truth for all module labels, subtitles, sidebar items,
 * breadcrumbs, and page titles. All strings reference i18n keys.
 */
import {
  Activity, AlertTriangle, BarChart3, Globe, Layers,
  Plane, Radar, Search, TrendingUp, FileSearch, Building2,
  Users, ShieldCheck,
} from "lucide-react";

export const PLATFORM_IDENTITY = {
  brandKey: "platform.brand",
  taglineKey: "platform.tagline",
  footerKey: "platform.footer",
};

export const MODULES = {
  executive: {
    id: "executive",
    path: "/executive",
    icon: Radar,
    titleKey: "modules.executive.title",
    navLabelKey: "modules.executive.navLabel",
    subtitleKey: "modules.executive.subtitle",
    accent: "signal",
    group: "intelligence",
  },
  reputation: {
    id: "reputation",
    path: "/reputation",
    icon: Activity,
    titleKey: "modules.reputation.title",
    subtitleKey: "modules.reputation.subtitle",
    accent: "risk",
    group: "intelligence",
  },
  forecasting: {
    id: "forecasting",
    path: "/forecasting",
    icon: TrendingUp,
    titleKey: "modules.forecasting.title",
    subtitleKey: "modules.forecasting.subtitle",
    accent: "warning",
    group: "intelligence",
  },
  benchmarking: {
    id: "benchmarking",
    path: "/benchmarking",
    icon: BarChart3,
    titleKey: "modules.benchmarking.title",
    subtitleKey: "modules.benchmarking.subtitle",
    accent: "signal",
    group: "intelligence",
  },
  anomalies: {
    id: "anomalies",
    path: "/anomalies",
    icon: AlertTriangle,
    titleKey: "modules.anomalies.title",
    subtitleKey: "modules.anomalies.subtitle",
    accent: "risk",
    group: "intelligence",
  },
  semantic: {
    id: "semantic",
    path: "/semantic",
    icon: Search,
    titleKey: "modules.semantic.title",
    navLabelKey: "modules.semantic.navLabel",
    subtitleKey: "modules.semantic.subtitle",
    accent: "signal",
    group: "intelligence",
  },
  aviation: {
    id: "aviation",
    path: "/aviation",
    icon: Plane,
    titleKey: "modules.aviation.title",
    subtitleKey: "modules.aviation.subtitle",
    accent: "signal",
    group: "aviation",
  },
  hubs: {
    id: "hubs",
    path: "/hubs",
    icon: Building2,
    titleKey: "modules.hubs.title",
    subtitleKey: "modules.hubs.subtitle",
    accent: "warning",
    group: "aviation",
  },
  alliances: {
    id: "alliances",
    path: "/alliances",
    icon: Users,
    titleKey: "modules.alliances.title",
    subtitleKey: "modules.alliances.subtitle",
    accent: "warning",
    group: "aviation",
  },
  coverage: {
    id: "coverage",
    path: "/coverage",
    icon: ShieldCheck,
    titleKey: "modules.coverage.title",
    subtitleKey: "modules.coverage.subtitle",
    accent: "signal",
    group: "aviation",
  },
  geospatial: {
    id: "geospatial",
    path: "/geospatial",
    icon: Globe,
    titleKey: "modules.geospatial.title",
    subtitleKey: "modules.geospatial.subtitle",
    accent: "signal",
    group: "spatial",
  },
  investigations: {
    id: "investigations",
    path: "/investigations",
    icon: FileSearch,
    titleKey: "modules.investigations.title",
    subtitleKey: "modules.investigations.subtitle",
    accent: "warning",
    group: "spatial",
  },
};

export const SIDEBAR_GROUPS = [
  {
    id: "intelligence",
    labelKey: "groups.intelligence",
    items: [
      MODULES.executive,
      MODULES.reputation,
      MODULES.forecasting,
      MODULES.benchmarking,
      MODULES.anomalies,
      MODULES.semantic,
    ],
  },
  {
    id: "aviation",
    labelKey: "groups.aviation",
    items: [
      MODULES.aviation,
      MODULES.hubs,
      MODULES.alliances,
      MODULES.coverage,
    ],
  },
  {
    id: "spatial",
    labelKey: "groups.spatial",
    items: [
      MODULES.geospatial,
      MODULES.investigations,
    ],
  },
];
