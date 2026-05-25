import React, { memo, useState, useCallback, useEffect } from "react";
import { NavLink } from "react-router-dom";
import { useTranslation } from "react-i18next";
import {
  Activity, AlertTriangle, BarChart3, Globe, Layers,
  Plane, Radar, Search, TrendingUp, FileSearch, Building2,
  Users, ShieldCheck, ChevronsLeft, ChevronsRight
} from "lucide-react";

const STORAGE_KEY = "skytrax-sidebar";

const GROUPS = [
  {
    id: "intelligence",
    labelKey: "nav.groupIntelligence",
    items: [
      { path: "/executive", icon: Radar, labelKey: "nav.executive" },
      { path: "/benchmarking", icon: BarChart3, labelKey: "nav.benchmarking" },
      { path: "/reputation", icon: Activity, labelKey: "nav.reputation" },
      { path: "/semantic", icon: Search, labelKey: "nav.semantic" },
      { path: "/forecasting", icon: TrendingUp, labelKey: "nav.forecasting" },
      { path: "/anomalies", icon: AlertTriangle, labelKey: "nav.anomalies" },
    ],
  },
  {
    id: "aviation",
    labelKey: "nav.groupAviation",
    items: [
      { path: "/aviation", icon: Plane, labelKey: "nav.aviationIntel" },
      { path: "/hubs", icon: Building2, labelKey: "nav.hubIntel" },
      { path: "/alliances", icon: Users, labelKey: "nav.allianceIntel" },
      { path: "/coverage", icon: ShieldCheck, labelKey: "nav.coverageIntel" },
    ],
  },
  {
    id: "spatial",
    labelKey: "nav.groupSpatial",
    items: [
      { path: "/geospatial", icon: Globe, labelKey: "nav.geospatial" },
      { path: "/investigations", icon: FileSearch, labelKey: "nav.investigations" },
    ],
  },
];

function getInitialCollapsed() {
  try {
    const v = localStorage.getItem(STORAGE_KEY);
    if (v === "collapsed") return true;
    if (v === "expanded") return false;
  } catch {}
  return window.innerWidth < 1024;
}

function SidebarInner() {
  const { t } = useTranslation("nav");
  const [collapsed, setCollapsed] = useState(getInitialCollapsed);
  const [mobileOpen, setMobileOpen] = useState(false);

  const toggle = useCallback(() => {
    setCollapsed((prev) => {
      const next = !prev;
      try { localStorage.setItem(STORAGE_KEY, next ? "collapsed" : "expanded"); } catch {}
      return next;
    });
  }, []);

  useEffect(() => {
    const mq = window.matchMedia("(max-width: 900px)");
    const handler = () => { if (mq.matches) setMobileOpen(false); };
    mq.addEventListener("change", handler);
    return () => mq.removeEventListener("change", handler);
  }, []);

  const closeMobile = useCallback(() => setMobileOpen(false), []);

  const sidebarCls = [
    "sidebar",
    collapsed ? "sidebar--collapsed" : "sidebar--expanded",
    mobileOpen ? "sidebar--mobile-open" : "",
  ].join(" ");

  return (
    <>
      {mobileOpen && <div className="sidebar-overlay" onClick={closeMobile} />}
      <aside className={sidebarCls} aria-label={t("sidebarLabel", { defaultValue: "Navigation" })}>
        <div className="sidebar-header">
          <div className="sidebar-brand">
            <Radar size={22} strokeWidth={1.75} />
            {!collapsed && <span className="sidebar-brand-text">SkyTrax Intel</span>}
          </div>
          <button
            type="button"
            className="sidebar-toggle"
            onClick={toggle}
            title={collapsed ? t("nav.expandSidebar", { defaultValue: "Expand navigation" }) : t("nav.collapseSidebar", { defaultValue: "Collapse navigation" })}
            aria-label={collapsed ? "Expand navigation" : "Collapse navigation"}
          >
            {collapsed ? <ChevronsRight size={16} /> : <ChevronsLeft size={16} />}
          </button>
        </div>

        <nav className="sidebar-nav">
          {GROUPS.map((group) => (
            <div className="sidebar-group" key={group.id}>
              {!collapsed && (
                <span className="sidebar-group-label">
                  {t(group.labelKey, { defaultValue: group.id })}
                </span>
              )}
              {collapsed && <div className="sidebar-group-dot" />}
              {group.items.map(({ path, icon: Icon, labelKey }) => (
                <NavLink
                  key={path}
                  to={path}
                  className={({ isActive }) =>
                    `sidebar-item ${isActive ? "sidebar-item--active" : ""}`
                  }
                  onClick={closeMobile}
                  {...(collapsed ? { "data-tooltip": t(labelKey) } : {})}
                >
                  <Icon size={18} strokeWidth={1.75} className="sidebar-item-icon" />
                  {!collapsed && (
                    <span className="sidebar-item-label">{t(labelKey)}</span>
                  )}
                </NavLink>
              ))}
            </div>
          ))}
        </nav>

        <div className="sidebar-footer">
          {!collapsed && (
            <span className="sidebar-footer-text">
              <Layers size={13} />
              Command Center
            </span>
          )}
          {collapsed && <Layers size={14} className="sidebar-footer-icon" />}
        </div>
      </aside>
    </>
  );
}

export const Sidebar = memo(SidebarInner);
