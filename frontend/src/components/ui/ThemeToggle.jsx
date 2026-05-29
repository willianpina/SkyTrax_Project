import React, { memo } from "react";
import { Sun, Moon } from "lucide-react";
import { useTheme } from "../../hooks/ThemeProvider";

function ThemeToggleInner() {
  const { theme, toggle } = useTheme();
  const isDark = theme === "dark";

  return (
    <button
      type="button"
      className="theme-toggle"
      onClick={toggle}
      aria-label={isDark ? "Switch to light mode" : "Switch to dark mode"}
      title={isDark ? "Light mode" : "Dark mode"}
    >
      {isDark ? <Sun size={13} /> : <Moon size={13} />}
    </button>
  );
}

export const ThemeToggle = memo(ThemeToggleInner);
