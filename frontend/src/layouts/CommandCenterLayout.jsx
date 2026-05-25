import React from "react";
import { Outlet } from "react-router-dom";
import { Sidebar } from "../navigation/Sidebar";
import { TopCommandBar } from "../navigation/TopCommandBar";

export default function CommandCenterLayout() {
  return (
    <main className="command-center">
      <Sidebar />
      <div className="command-main">
        <TopCommandBar />
        <div className="workspace-viewport">
          <React.Suspense
            fallback={
              <div className="workspace-loading">
                <div className="boot-scan" aria-hidden />
                <p>Loading workspace…</p>
              </div>
            }
          >
            <Outlet />
          </React.Suspense>
        </div>
      </div>
    </main>
  );
}
