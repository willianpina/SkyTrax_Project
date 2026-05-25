import React, { createContext, useContext } from "react";
import { useAnalytics } from "./useAnalytics";

const AnalyticsContext = createContext(null);

export function AnalyticsProvider({ children }) {
  const analytics = useAnalytics();
  return (
    <AnalyticsContext.Provider value={analytics}>
      {children}
    </AnalyticsContext.Provider>
  );
}

export function useSharedAnalytics() {
  const ctx = useContext(AnalyticsContext);
  if (!ctx) throw new Error("useSharedAnalytics must be used within AnalyticsProvider");
  return ctx;
}
