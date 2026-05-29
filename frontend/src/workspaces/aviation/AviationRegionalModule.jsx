import React, { memo, useMemo } from "react";
import { useTranslation } from "react-i18next";
import { Globe } from "lucide-react";
import { OperationalModuleCard } from "../../components/forecasting/OperationalModuleCard";

function AviationRegionalModuleInner({ regions = [], loading }) {
  const { t } = useTranslation("aviation");
  const rows = useMemo(() => (regions || []).slice(0, 12), [regions]);
  const maxCount = Math.max(1, ...rows.map((r) => r.airline_count || 0));
  const isEmpty = !loading && rows.length === 0;

  return (
    <OperationalModuleCard
      className="aviation-regional-module"
      title={t("regionalTitle")}
      subtitle={
        rows.length ? t("regionalSubtitleCount", { count: rows.length }) : t("regionalSubtitle")
      }
      expandable
      defaultExpanded={rows.length > 0}
      bodyClassName="aviation-regional-module__body"
    >
      {loading && isEmpty ? (
        <div className="aviation-module-skeleton" />
      ) : isEmpty ? (
        <div className="aviation-empty-runtime aviation-empty-runtime--compact">
          <Globe size={18} strokeWidth={1.2} aria-hidden />
          <p className="aviation-empty-runtime__title">{t("emptyRegionalTitle")}</p>
          <p className="aviation-empty-runtime__detail">{t("emptyRegionalDetail")}</p>
        </div>
      ) : (
        <ul className="aviation-regional-list" role="list">
          {rows.map((r, i) => (
            <li className="aviation-regional-row" key={r.country} role="listitem">
              <div className="aviation-regional-row-top">
                <span className="aviation-regional-rank">#{i + 1}</span>
                <strong className="aviation-regional-name">{r.country}</strong>
                <span className="aviation-regional-count">
                  {t("carrierCount", { count: r.airline_count })}
                </span>
              </div>
              <div className="aviation-weight-track" aria-hidden>
                <div
                  className="aviation-weight-fill aviation-weight-fill--regional"
                  style={{ width: `${((r.airline_count || 0) / maxCount) * 100}%` }}
                />
              </div>
              {r.avg_star_rating ? (
                <span className="aviation-regional-rating">
                  {t("avgRating", { value: r.avg_star_rating })}
                </span>
              ) : null}
            </li>
          ))}
        </ul>
      )}
    </OperationalModuleCard>
  );
}

export const AviationRegionalModule = memo(AviationRegionalModuleInner);
