import React, { memo } from "react";
import { NavLink } from "react-router-dom";
import { useTranslation } from "react-i18next";
import {
  Activity, AlertTriangle, BarChart3, Globe, Layers,
  Radar, Search, TrendingUp, FileSearch
} from "lucide-react";

const WORKSPACE_NAV = [
  { path: "/executive", icon: Radar, labelKey: "nav.executive" },
  { path: "/benchmarking", icon: BarChart3, labelKey: "nav.benchmarking" },
  { path: "/reputation", icon: Activity, labelKey: "nav.reputation" },
  { path: "/semantic", icon: Search, labelKey: "nav.semantic" },
  { path: "/forecasting", icon: TrendingUp, labelKey: "nav.forecasting" },
  { path: "/anomalies", icon: AlertTriangle, labelKey: "nav.anomalies" },
  { path: "/geospatial", icon: Globe, labelKey: "nav.geospatial" },
  { path: "/investigations", icon: FileSearch, labelKey: "nav.investigations" }
];

function SidebarInner() {
  const { t } = useTranslation("nav");

  return (
    <aside className="command-rail" aria-label={t("sidebarLabel")}>
      <div className="rail-brand" title={t("brand")}>
        <Radar size={20} strokeWidth={1.75} />
      </div>
      <nav className="rail-nav">
        {WORKSPACE_NAV.map(({ path, icon: Icon, labelKey }) => (
          <NavLink
            key={path}
            to={path}
            className={({ isActive }) => `rail-btn ${isActive ? "active" : ""}`}
            title={t(labelKey)}
          >
            <Icon size={16} strokeWidth={1.75} />
            <span className="rail-label">{t(labelKey)}</span>
          </NavLink>
        ))}
      </nav>
      <div className="rail-footer">
        <Layers size={14} className="muted-icon" />
      </div>
    </aside>
  );
}

export const Sidebar = memo(SidebarInner);
