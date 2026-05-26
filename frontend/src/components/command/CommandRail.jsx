import React, { memo } from "react";
import { useTranslation } from "react-i18next";
import { Activity, BarChart3, Layers, Radar, Search } from "lucide-react";
import { safeT } from "../../utils/i18nSafety";

const NAV = [
  { id: "executive", icon: Radar, key: "modules.executive.title" },
  { id: "benchmark", icon: BarChart3, key: "modules.benchmarking.title" },
  { id: "reputation", icon: Activity, key: "modules.reputation.title" },
  { id: "semantic", icon: Search, key: "modules.semantic.title" },
  { id: "layers", icon: Layers, key: "command:nav.operations" },
];

function CommandRailInner({ activeSection = "executive", signalCount = 0, isLive }) {
  const { t } = useTranslation(["nav", "command", "common"]);

  return (
    <aside className="command-rail" aria-label={t("command:rail.label")}>
      <div className="rail-brand" title={t("common:brand")}>
        <Radar size={20} strokeWidth={1.75} />
        <span className="rail-status" data-live={isLive} aria-hidden />
      </div>
      <nav className="rail-nav">
        {NAV.map(({ id, icon: Icon, key }) => (
          <button
            key={id}
            type="button"
            className={`rail-btn ${activeSection === id ? "active" : ""}`}
            title={safeT(t, key, id)}
            aria-current={activeSection === id ? "page" : undefined}
          >
            <Icon size={16} strokeWidth={1.75} />
            <span className="rail-label">{safeT(t, key, id)}</span>
          </button>
        ))}
      </nav>
      {signalCount > 0 ? (
        <div className="rail-signals">
          <span className="signal-count">{signalCount}</span>
          <span className="rail-label">{t("command:rail.signals")}</span>
        </div>
      ) : null}
    </aside>
  );
}

export const CommandRail = memo(CommandRailInner);
