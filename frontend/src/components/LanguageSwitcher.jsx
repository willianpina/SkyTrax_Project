import React from "react";
import { useTranslation } from "react-i18next";
import { Globe } from "lucide-react";
import { changeAppLanguage } from "../i18n";

export function LanguageSwitcher() {
  const { i18n, t } = useTranslation("common");
  const current = i18n.language?.startsWith("pt") ? "pt" : "en";

  const setLanguage = async (lng) => {
    if (lng === current) return;
    await changeAppLanguage(lng);
  };

  return (
    <div className="language-switcher" role="group" aria-label={t("language.label")}>
      <Globe size={14} strokeWidth={1.75} aria-hidden />
      <button
        type="button"
        className={`lang-pill ${current === "en" ? "active" : ""}`}
        onClick={() => setLanguage("en")}
        aria-pressed={current === "en"}
      >
        {t("language.en")}
      </button>
      <span className="lang-divider" aria-hidden>
        |
      </span>
      <button
        type="button"
        className={`lang-pill ${current === "pt" ? "active" : ""}`}
        onClick={() => setLanguage("pt")}
        aria-pressed={current === "pt"}
      >
        {t("language.pt")}
      </button>
    </div>
  );
}
