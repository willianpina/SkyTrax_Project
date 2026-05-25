import React, { memo } from "react";
import { NavLink } from "react-router-dom";
import { useTranslation } from "react-i18next";
import {
  Activity, AlertTriangle, BarChart3, Globe, Layers,
  Plane, Radar, Search, TrendingUp, FileSearch, Building2, Users, ShieldCheck
} from "lucide-react";

const WORKSPACE_NAV = [
  { path: "/executive", icon: Radar, labelKey: "nav.executive", group: "ops" },
  { path: "/benchmarking", icon: BarChart3, labelKey: "nav.benchmarking", group: "ops" },
  { path: "/reputation", icon: Activity, labelKey: "nav.reputation", group: "ops" },
  { path: "/semantic", icon: Search, labelKey: "nav.semantic", group: "ops" },
  { path: "/forecasting", icon: TrendingUp, labelKey: "nav.forecasting", group: "ops" },
  { path: "/anomalies", icon: AlertTriangle, labelKey: "nav.anomalies", group: "ops" },
  { path: "/aviation", icon: Plane, labelKey: "nav.aviationIntel", group: "aviation" },
  { path: "/hubs", icon: Building2, labelKey: "nav.hubIntel", group: "aviation" },
  { path: "/alliances", icon: Users, labelKey: "nav.allianceIntel", group: "aviation" },
  { path: "/coverage", icon: ShieldCheck, labelKey: "nav.coverageIntel", group: "aviation" },
  { path: "/geospatial", icon: Globe, labelKey: "nav.geospatial", group: "platform" },
  { path: "/investigations", icon: FileSearch, labelKey: "nav.investigations", group: "platform" }
];

function SidebarInner() {
  const { t } = useTranslation("nav");

  return (
    <aside className="command-rail" aria-label={t("sidebarLabel")}>
      <div className="rail-brand" title={t("brand")}>
        <Radar size={20} strokeWidth={1.75} />
      </div>
      <nav className="rail-nav">
        {WORKSPACE_NAV.map(({ path, icon: Icon, labelKey, group }, idx) => {
          const prev = WORKSPACE_NAV[idx - 1];
          const showSep = prev && prev.group !== group;
          return (
            <React.Fragment key={path}>
              {showSep && <div className="rail-separator" />}
              <NavLink
                to={path}
                className={({ isActive }) => `rail-btn ${isActive ? "active" : ""}`}
                title={t(labelKey)}
              >
                <Icon size={16} strokeWidth={1.75} />
                <span className="rail-label">{t(labelKey)}</span>
              </NavLink>
            </React.Fragment>
          );
        })}
      </nav>
      <div className="rail-footer">
        <Layers size={14} className="muted-icon" />
      </div>
    </aside>
  );
}

export const Sidebar = memo(SidebarInner);
