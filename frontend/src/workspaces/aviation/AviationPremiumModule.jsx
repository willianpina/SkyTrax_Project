import React, { memo } from "react";
import { useTranslation } from "react-i18next";
import { Crown } from "lucide-react";
import { OperationalModuleCard } from "../../components/forecasting/OperationalModuleCard";

function AviationPremiumModuleInner({ premium = [], loading }) {
  const { t } = useTranslation("aviation");
  const rows = (premium || []).slice(0, 8);
  const isEmpty = !loading && rows.length === 0;

  return (
    <OperationalModuleCard
      className="aviation-premium-module"
      title={t("premiumTitle")}
      subtitle={
        rows.length ? t("premiumSubtitleCount", { count: rows.length }) : t("premiumSubtitle")
      }
      expandable
      defaultExpanded={rows.length > 0}
      bodyClassName="aviation-premium-module__body"
    >
      {loading && isEmpty ? (
        <div className="aviation-module-skeleton" />
      ) : isEmpty ? (
        <div className="aviation-empty-runtime aviation-empty-runtime--compact">
          <Crown size={18} strokeWidth={1.2} aria-hidden />
          <p className="aviation-empty-runtime__title">{t("emptyPremiumTitle")}</p>
          <p className="aviation-empty-runtime__detail">{t("emptyPremiumDetail")}</p>
        </div>
      ) : (
        <ul className="aviation-insight-list" role="list">
          {rows.map((a, i) => (
            <li className="aviation-insight-card" key={a.slug} role="listitem">
              <span className="aviation-insight-rank">#{i + 1}</span>
              <div className="aviation-insight-body">
                <strong className="aviation-insight-title">{a.name}</strong>
                <span className="aviation-insight-meta">{a.country || "—"}</span>
              </div>
              <div className="aviation-insight-trail">
                <span className="aviation-stars-filled">{"★".repeat(a.star_rating || 0)}</span>
                {a.avg_rating != null ? (
                  <span className="aviation-insight-score">{a.avg_rating}</span>
                ) : null}
              </div>
            </li>
          ))}
        </ul>
      )}
    </OperationalModuleCard>
  );
}

export const AviationPremiumModule = memo(AviationPremiumModuleInner);
