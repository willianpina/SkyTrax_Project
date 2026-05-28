import React, { memo, useState, useCallback } from "react";
import { useTranslation } from "react-i18next";
import { Download, RefreshCw, Radio } from "lucide-react";
import { LanguageSwitcher } from "../components/LanguageSwitcher";
import { ThemeToggle } from "../components/ui/ThemeToggle";
import { OperationalSyncModal } from "../components/OperationalSyncModal";
import { useSharedAnalytics } from "../hooks/AnalyticsProvider";
import { useOperations } from "../hooks/useOperations";
import { usePlatformHealth } from "../hooks/usePlatformHealth";
import { exportReputationCsv } from "../lib/chartConfigs";

function TopCommandBarInner() {
  const { t } = useTranslation(["nav", "common", "command"]);
  const { isLive, isLoading, error, partialErrors, reload, reputation, benchmarking } = useSharedAnalytics();
  const [modalOpen, setModalOpen] = useState(false);
  const { status, history, loading, triggerRefresh, resetPipeline } = useOperations();
  const { badges: platformBadges, operationalHealth } = usePlatformHealth(45000, {
    enabled: !modalOpen,
    pipelineOnly: true,
  });

  const isStalled = status.stage === "stalled" || status.pipeline_status === "stalled" || !!status.stale;
  const isRefreshing = status.running === true && !isStalled;

  const handleSyncClick = useCallback(async () => {
    if (isStalled) {
      await resetPipeline();
      await triggerRefresh();
      setModalOpen(true);
      return;
    }
    if (isRefreshing) {
      setModalOpen(true);
      return;
    }
    await triggerRefresh();
    setModalOpen(true);
  }, [isRefreshing, isStalled, triggerRefresh, resetPipeline]);

  const streamStatus = (() => {
    if (isRefreshing) return "Syncing";
    if (isStalled) return "Delayed";
    if (isLive) return "Live";
    return "Standby";
  })();
  const streamLabel = streamStatus === "Live"
    ? t("command:ops.stream.live", { defaultValue: "Live ingestion active" })
    : streamStatus === "Syncing"
      ? t("command:ops.stream.syncing", { defaultValue: "Sync active" })
      : streamStatus === "Delayed"
        ? t("command:ops.stream.delayed", { defaultValue: "Sync delayed" })
        : t("command:ops.stream.standby", { defaultValue: "Ingestion standby" });
  const partialSuffix = partialErrors.length ? ` · ${t("common:status.partial", { count: partialErrors.length })}` : "";
  const streamTitle = [streamLabel, !isLive && error ? error : "", partialSuffix].filter(Boolean).join(" · ");

  return (
    <>
      <header className="command-header">
        <div className="topbar-brand">
          <span className="topbar-brand-name">{t("command:title")}</span>
          {platformBadges.length > 0 && (
            <div className="osm-platform-badges osm-platform-badges--compact">
              {platformBadges.map((b) => (
                <span
                  key={b.key}
                  className={`osm-platform-badge osm-platform-badge--${b.variant || b.severity}`}
                  title={b.tooltip || b.title || b.label}
                >
                  {b.label}
                </span>
              ))}
            </div>
          )}
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
          <div className="topbar-stream-group">
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
            <span
              className={`ops-stream-status ops-stream-status--${streamStatus.toLowerCase()}`}
              title={streamTitle}
              aria-label={streamTitle}
            >
              <span className="pulse-dot" aria-hidden />
              <span className="ops-stream-label">{streamLabel}</span>
            </span>
          </div>
        </div>
      </header>
      <OperationalSyncModal
        isOpen={modalOpen}
        onClose={() => setModalOpen(false)}
        status={status}
        history={history}
        onReset={resetPipeline}
        onRetrySync={handleSyncClick}
      />
    </>
  );
}

export const TopCommandBar = memo(TopCommandBarInner);
