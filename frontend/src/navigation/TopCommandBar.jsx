import React, { memo } from "react";
import { useTranslation } from "react-i18next";
import { useLocation } from "react-router-dom";
import { Download, RefreshCw } from "lucide-react";
import { LanguageSwitcher } from "../components/LanguageSwitcher";
import { useSharedAnalytics } from "../hooks/AnalyticsProvider";
import { exportReputationCsv } from "../lib/chartConfigs";

const WORKSPACE_LABELS = {
  "/executive": "nav.executive",
  "/benchmarking": "nav.benchmarking",
  "/reputation": "nav.reputation",
  "/semantic": "nav.semantic",
  "/forecasting": "nav.forecasting",
  "/anomalies": "nav.anomalies",
  "/geospatial": "nav.geospatial",
  "/investigations": "nav.investigations",
  "/aviation": "nav.aviationIntel",
  "/hubs": "nav.hubIntel",
  "/alliances": "nav.allianceIntel"
};

function TopCommandBarInner() {
  const { t } = useTranslation(["nav", "common", "command"]);
  const { isLive, isLoading, error, partialErrors, reload, reputation, benchmarking } = useSharedAnalytics();
  const location = useLocation();

  const workspaceKey = WORKSPACE_LABELS[location.pathname] || "nav.executive";
  const statusLabel = isLive ? t("common:status.apiLive") : error || t("common:status.demoData");
  const partialSuffix = partialErrors.length ? ` · ${t("common:status.partial", { count: partialErrors.length })}` : "";

  return (
    <header className="command-header glass-panel">
      <div>
        <p className="eyebrow">{t("command:title")}</p>
        <h1 className="topbar-workspace-title">{t(workspaceKey)}</h1>
      </div>
      <div className="topbar-actions">
        <LanguageSwitcher />
        <button
          type="button"
          className="tactical-btn icon"
          onClick={() => exportReputationCsv(reputation, benchmarking?.complaint_density)}
          title={t("common:actions.exportCsv")}
        >
          <Download size={14} />
        </button>
        <button
          type="button"
          className="tactical-btn icon"
          onClick={reload}
          title={t("common:actions.reload")}
        >
          <RefreshCw size={14} className={isLoading ? "spin" : ""} />
        </button>
        <span className={`ops-status ${isLive ? "live" : ""}`}>
          <span className="pulse-dot" aria-hidden />
          {statusLabel}{partialSuffix}
        </span>
      </div>
    </header>
  );
}

export const TopCommandBar = memo(TopCommandBarInner);
