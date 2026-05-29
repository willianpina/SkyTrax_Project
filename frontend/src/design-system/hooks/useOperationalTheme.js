import { useEffect, useMemo, useState } from "react";

export function useOperationalTheme() {
  const getTheme = () => document?.documentElement?.getAttribute("data-theme") || "dark";
  const [theme, setTheme] = useState(getTheme);

  useEffect(() => {
    const observer = new MutationObserver(() => setTheme(getTheme()));
    observer.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ["data-theme"],
    });
    return () => observer.disconnect();
  }, []);

  const telemetryTags = useMemo(() => ({
    DESIGN_SYSTEM: "SODS.v1",
    THEME_RUNTIME: `theme:${theme}`,
    LAYOUT_GOVERNANCE: "operational-layout",
  }), [theme]);

  return {
    theme,
    isDark: theme !== "light",
    telemetryTags,
  };
}
