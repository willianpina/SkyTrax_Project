import React, { memo, useState, useCallback } from "react";
import { useTranslation } from "react-i18next";
import { useLocation } from "react-router-dom";
import { Download, RefreshCw, Radio } from "lucide-react";
import { LanguageSwitcher } from "../components/LanguageSwitcher";
import { ThemeToggle } from "../components/ui/ThemeToggle";
import { OperationalSyncModal } from "../components/OperationalSyncModal";
import { useSharedAnalytics } from "../hooks/AnalyticsProvider";
import { useOperations } from "../hooks/useOperations";
import { exportReputationCsv } from "../lib/chartConfigs";
import { safeT } from "../utils/i18nSafety";

const WORKSPACE_LABELS = {
  "/executive": "modules.executive.title",
  "/benchmarking": "modules.benchmarking.title",
  "/reputation": "modules.reputation.title",
  "/semantic": "modules.semantic.title",
  "/forecasting": "modules.forecasting.title",
  "/anomalies": "modules.anomalies.title",
  "/geospatial": "modules.geospatial.title",
  "/investigations": "modules.investigations.title",
  "/aviation": "modules.aviation.title",
  "/hubs": "modules.hubs.title",
  "/alliances": "modules.alliances.title",
  "/coverage": "modules.coverage.title",
};

function TopCommandBarInner() {
  const { t } = useTranslation(["nav", "common", "command"]);
  const { isLive, isLoading, error, partialErrors, reload, reputation, benchmarking } = useSharedAnalytics();
  const { status, history, loading, triggerRefresh } = useOperations();
  const location = useLocation();
  const [modalOpen, setModalOpen] = useState(false);

  const workspaceKey = WORKSPACE_LABELS[location.pathname] || "modules.executive.title";
  const isRefreshing = status.running === true;

  const handleSyncClick = useCallback(async () => {
    if (isRefreshing) {
      setModalOpen(true);
      return;
    }
    await triggerRefresh();
    setModalOpen(true);
  }, [isRefreshing, triggerRefresh]);

  const statusLabel = isLive ? "LIVE" : error || t("common:status.demoData");
  const partialSuffix = partialErrors.length ? ` · ${t("common:status.partial", { count: partialErrors.length })}` : "";

  return (
    <>
      <header className="command-header glass-panel">
        <div>
          <p className="eyebrow">{t("command:title")}</p>
          <h1 className="topbar-workspace-title">{safeT(t, workspaceKey, "Command Center")}</h1>
        </div>
        <div className="topbar-actions">
          <ThemeToggle />
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
          <button
            type="button"
            className={`ops-sync-btn ${isRefreshing ? "syncing" : ""}`}
            onClick={handleSyncClick}
            disabled={loading}
            title={t("command:ops.syncTitle")}
          >
            <Radio size={14} className={isRefreshing ? "pulse-icon" : ""} />
            <span>{isRefreshing ? t("command:ops.synchronizing") : t("command:ops.sync")}</span>
          </button>
          <span className={`ops-status ${isLive ? "live" : ""}`}>
            <span className="pulse-dot" aria-hidden />
            {statusLabel}{partialSuffix}
          </span>
        </div>
      </header>
      <OperationalSyncModal
        isOpen={modalOpen}
        onClose={() => setModalOpen(false)}
        status={status}
        history={history}
      />
    </>
  );
}

export const TopCommandBar = memo(TopCommandBarInner);
