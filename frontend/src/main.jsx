import React from "react";
import { createRoot } from "react-dom/client";
import { RouterProvider } from "react-router-dom";
import { I18nextProvider } from "react-i18next";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { AnalyticsProvider } from "./hooks/AnalyticsProvider";
import { router } from "./router";
import i18n, { initI18n } from "./i18n";
import "./styles.css";

function AppBootstrap() {
  const [ready, setReady] = React.useState(i18n.isInitialized);

  React.useEffect(() => {
    if (i18n.isInitialized) return;
    initI18n().then(() => setReady(true));
  }, []);

  if (!ready) {
    return (
      <div className="app-loading command-boot">
        <div className="boot-scan" aria-hidden />
        <p>{i18n.t("common:status.loading", { defaultValue: "Loading command center…" })}</p>
      </div>
    );
  }

  return (
    <I18nextProvider i18n={i18n}>
      <ErrorBoundary>
        <AnalyticsProvider>
          <RouterProvider router={router} />
        </AnalyticsProvider>
      </ErrorBoundary>
    </I18nextProvider>
  );
}

createRoot(document.getElementById("root")).render(<AppBootstrap />);
