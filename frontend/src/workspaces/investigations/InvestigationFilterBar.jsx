import React, { memo } from "react";
import { useTranslation } from "react-i18next";
import { Filter } from "lucide-react";

function InvestigationFilterBarInner({ airlines, selectedAirline, onChange }) {
  const { t } = useTranslation("investigations");

  return (
    <div className="investigation-filter-bar">
      <label className="investigation-filter-label">
        <Filter size={13} aria-hidden />
        {t("filterLabel")}
      </label>
      <select
        className="investigation-filter-select"
        value={selectedAirline}
        onChange={(e) => onChange(e.target.value)}
      >
        <option value="">{t("filterAll")}</option>
        {airlines.map((a) => (
          <option key={a.slug} value={a.slug}>
            {a.name}
          </option>
        ))}
      </select>
    </div>
  );
}

export const InvestigationFilterBar = memo(InvestigationFilterBarInner);
