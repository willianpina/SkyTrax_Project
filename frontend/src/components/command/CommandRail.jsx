import React, { memo } from "react";
import { useTranslation } from "react-i18next";
import { Activity, BarChart3, Layers, Radar, Search } from "lucide-react";

const NAV = [
  { id: "executive", icon: Radar, ns: "dashboard", key: "nav.executiveView" },
  { id: "benchmark", icon: BarChart3, ns: "dashboard", key: "nav.benchmarking" },
  { id: "reputation", icon: Activity, ns: "dashboard", key: "nav.reputation" },
  { id: "semantic", icon: Search, ns: "dashboard", key: "nav.semanticOps" },
  { id: "layers", icon: Layers, ns: "command", key: "nav.operations" }
];

function CommandRailInner({ activeSection = "executive", signalCount = 0, isLive }) {
  const { t } = useTranslation(["dashboard", "command", "common"]);

  return (
    <aside className="command-rail" aria-label={t("command:rail.label")}>
      <div className="rail-brand" title={t("common:brand")}>
        <Radar size={20} strokeWidth={1.75} />
        <span className="rail-status" data-live={isLive} aria-hidden />
      </div>
      <nav className="rail-nav">
        {NAV.map(({ id, icon: Icon, ns, key }) => (
          <button
            key={id}
            type="button"
            className={`rail-btn ${activeSection === id ? "active" : ""}`}
            title={t(`${ns}:${key}`)}
            aria-current={activeSection === id ? "page" : undefined}
          >
            <Icon size={16} strokeWidth={1.75} />
            <span className="rail-label">{t(`${ns}:${key}`)}</span>
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
