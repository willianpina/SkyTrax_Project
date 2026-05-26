import React, { memo, useState, useCallback, useEffect } from "react";
import { NavLink } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Layers, ChevronsLeft, ChevronsRight, Radar } from "lucide-react";
import { SIDEBAR_GROUPS, PLATFORM_IDENTITY } from "../config/navigation";

const STORAGE_KEY = "skytrax-sidebar";

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
      <aside className={sidebarCls} aria-label={t("sidebarLabel")}>
        <div className="sidebar-header">
          <div className="sidebar-brand">
            <Radar size={22} strokeWidth={1.75} />
            {!collapsed && (
              <div className="sidebar-brand-block">
                <span className="sidebar-brand-text">
                  {t(PLATFORM_IDENTITY.brandKey)}
                </span>
                <span className="sidebar-brand-tagline">
                  {t(PLATFORM_IDENTITY.taglineKey)}
                </span>
              </div>
            )}
          </div>
          <button
            type="button"
            className="sidebar-toggle"
            onClick={toggle}
            title={collapsed ? t("nav.expandSidebar") : t("nav.collapseSidebar")}
            aria-label={collapsed ? "Expand navigation" : "Collapse navigation"}
          >
            {collapsed ? <ChevronsRight size={16} /> : <ChevronsLeft size={16} />}
          </button>
        </div>

        <nav className="sidebar-nav">
          {SIDEBAR_GROUPS.map((group) => (
            <div className={`sidebar-group sidebar-group--${group.id}`} key={group.id}>
              {!collapsed && (
                <span className="sidebar-group-label">
                  {t(group.labelKey)}
                </span>
              )}
              {collapsed && <div className="sidebar-group-dot" />}
              {group.items.map(({ path, icon: Icon, titleKey }) => (
                <NavLink
                  key={path}
                  to={path}
                  className={({ isActive }) =>
                    `sidebar-item ${isActive ? "sidebar-item--active" : ""}`
                  }
                  onClick={closeMobile}
                  {...(collapsed ? { "data-tooltip": t(titleKey) } : {})}
                >
                  <Icon size={18} strokeWidth={1.75} className="sidebar-item-icon" />
                  {!collapsed && (
                    <span className="sidebar-item-label">{t(titleKey)}</span>
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
              {t(PLATFORM_IDENTITY.footerKey)}
            </span>
          )}
          {collapsed && <Layers size={14} className="sidebar-footer-icon" />}
        </div>
      </aside>
    </>
  );
}

export const Sidebar = memo(SidebarInner);
