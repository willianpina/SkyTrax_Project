import React, { memo, useState } from "react";
import { useTranslation } from "react-i18next";
import { Plane } from "lucide-react";
import { OperationalModuleCard } from "../../components/forecasting/OperationalModuleCard";
import { ALLIANCE_COLORS, formatAirlineType } from "./aviationShared";

function TypeBadge({ typeInfo }) {
  if (!typeInfo) return <span className="aviation-muted">—</span>;
  const obClass =
    typeInfo.variant === "warning"
      ? "ob--warning"
      : typeInfo.variant === "info"
        ? "ob--info"
        : "ob--neutral";
  return <span className={`ob ${obClass}`}>{typeInfo.label}</span>;
}

function AviationRegistryInner({ airlines = [], loading }) {
  const { t } = useTranslation("aviation");
  const [limit, setLimit] = useState(40);
  const displayed = airlines.slice(0, limit);
  const isEmpty = !loading && airlines.length === 0;

  return (
    <OperationalModuleCard
      className="aviation-registry-module"
      title={t("registryTitle")}
      subtitle={t("registrySubtitle", { count: airlines.length })}
      expandable
      defaultExpanded
      bodyClassName="aviation-registry-module__body"
    >
      {isEmpty ? (
        <div className="aviation-empty-runtime">
          <Plane size={22} strokeWidth={1.2} aria-hidden />
          <p className="aviation-empty-runtime__title">{t("emptyRegistryTitle")}</p>
          <p className="aviation-empty-runtime__detail">{t("emptyRegistryDetail")}</p>
        </div>
      ) : (
        <>
          <div className="aviation-runtime-scroll">
            <div className="aviation-runtime-head" role="row">
              <span>{t("table.airline")}</span>
              <span>{t("table.country")}</span>
              <span>{t("table.type")}</span>
              <span>{t("table.rating")}</span>
              <span>{t("table.alliance")}</span>
              <span>{t("table.confidence")}</span>
            </div>
            {displayed.map((a) => {
              const typeInfo = formatAirlineType(a.airline_type, t);
              const allianceColor = ALLIANCE_COLORS[a.alliance] || "var(--text-dim)";
              const conf = Math.round((a.enrichment_confidence || 0) * 100);
              return (
                <div className="aviation-runtime-row" key={a.slug} role="row">
                  <span className="aviation-runtime-airline">
                    <Plane size={12} aria-hidden />
                    <strong>{a.name}</strong>
                  </span>
                  <span className="aviation-runtime-cell">{a.country || "—"}</span>
                  <span className="aviation-runtime-cell">
                    <TypeBadge typeInfo={typeInfo} />
                  </span>
                  <span className="aviation-runtime-cell aviation-runtime-stars">
                    {a.star_rating ? (
                      <>
                        <span className="aviation-stars-filled">{"★".repeat(a.star_rating)}</span>
                        <span className="aviation-stars-dim">
                          {"★".repeat(Math.max(0, 5 - a.star_rating))}
                        </span>
                      </>
                    ) : (
                      "—"
                    )}
                  </span>
                  <span className="aviation-runtime-cell">
                    {a.alliance ? (
                      <span
                        className="aviation-alliance-pill"
                        style={{ "--alliance-accent": allianceColor }}
                      >
                        {a.alliance}
                      </span>
                    ) : (
                      <span className="aviation-muted">{t("independent")}</span>
                    )}
                  </span>
                  <span className="aviation-runtime-cell aviation-runtime-conf">
                    <span className="aviation-conf-track" title={`${conf}%`}>
                      <span className="aviation-conf-fill" style={{ width: `${conf}%` }} />
                    </span>
                    <span className="aviation-conf-pct">{conf}%</span>
                  </span>
                </div>
              );
            })}
          </div>
          {airlines.length > limit ? (
            <button
              type="button"
              className="aviation-load-more"
              onClick={() => setLimit((n) => n + 40)}
            >
              {t("showMore", { count: airlines.length - limit })}
            </button>
          ) : null}
        </>
      )}
    </OperationalModuleCard>
  );
}

export const AviationRegistry = memo(AviationRegistryInner);
