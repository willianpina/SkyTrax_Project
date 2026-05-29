import React, { memo } from "react";
import { useTranslation } from "react-i18next";
import { Globe, TrendingDown, TrendingUp, Minus } from "lucide-react";
import { OperationalModuleCard } from "../../components/forecasting/OperationalModuleCard";
import { formatScore } from "../../utils/formatMetric";
import { ALLIANCE_THEME, riskLevel, sortAlliances } from "./allianceShared";

function TrendIcon({ risk }) {
  if (risk > 50) return <TrendingDown size={13} className="alliance-trend alliance-trend--down" aria-hidden />;
  if (risk < 20) return <TrendingUp size={13} className="alliance-trend alliance-trend--up" aria-hidden />;
  return <Minus size={13} className="alliance-trend alliance-trend--flat" aria-hidden />;
}

function AlliancePanoramaCard({ alliance }) {
  const { t } = useTranslation("alliances");
  const theme = ALLIANCE_THEME[alliance.name] || { accent: "#94a3b8" };
  const risk = alliance.operational_risk || 0;
  const members = alliance.members || [];
  const topMembers = members.slice(0, 5);

  return (
    <article
      className="alliance-panorama-card"
      style={{ "--alliance-accent": theme.accent }}
    >
      <header className="alliance-panorama-card__head">
        <div className="alliance-panorama-card__title">
          <span className="alliance-panorama-dot" aria-hidden />
          <h3>{alliance.name}</h3>
        </div>
        <TrendIcon risk={risk} />
      </header>

      <div className="alliance-panorama-metrics">
        <div className="alliance-panorama-metric">
          <span className="alliance-panorama-metric-val">{formatScore(alliance.avg_rating)}</span>
          <span className="alliance-panorama-metric-lbl">{t("cardRating")}</span>
        </div>
        <div className="alliance-panorama-metric">
          <span className="alliance-panorama-metric-val">{alliance.member_count || "—"}</span>
          <span className="alliance-panorama-metric-lbl">{t("cardMembers")}</span>
        </div>
        <div className="alliance-panorama-metric">
          <span className="alliance-panorama-metric-val">
            {(alliance.total_reviews || 0).toLocaleString()}
          </span>
          <span className="alliance-panorama-metric-lbl">{t("cardReviews")}</span>
        </div>
        <div className={`alliance-panorama-metric alliance-panorama-metric--${riskLevel(risk)}`}>
          <span className="alliance-panorama-metric-val">{formatScore(risk)}</span>
          <span className="alliance-panorama-metric-lbl">{t("cardRisk")}</span>
        </div>
      </div>

      {topMembers.length > 0 ? (
        <ul className="alliance-panorama-members" role="list">
          {topMembers.map((m) => (
            <li className="alliance-panorama-member" key={m.slug}>
              <span>{m.name}</span>
              <span className="alliance-panorama-stars" aria-label={`${m.star_rating || 0} stars`}>
                {"★".repeat(m.star_rating || 0)}
                {"☆".repeat(Math.max(0, 5 - (m.star_rating || 0)))}
              </span>
            </li>
          ))}
          {members.length > 5 ? (
            <li className="alliance-panorama-more">{t("cardMore", { count: members.length - 5 })}</li>
          ) : null}
        </ul>
      ) : null}
    </article>
  );
}

function AlliancePanoramaPanelInner({ alliances, loading }) {
  const { t } = useTranslation("alliances");
  const sorted = sortAlliances(alliances);
  const isEmpty = !loading && sorted.length === 0;

  return (
    <OperationalModuleCard
      className="alliance-panorama-module"
      title={t("panoramaTitle")}
      subtitle={t("panoramaSubtitle")}
      expandable
      defaultExpanded
      bodyClassName="alliance-panorama-module__body"
    >
      {loading && isEmpty ? (
        <div className="alliance-module-skeleton" />
      ) : isEmpty ? (
        <div className="alliance-empty-runtime alliance-empty-runtime--compact">
          <Globe size={18} strokeWidth={1.2} aria-hidden />
          <p className="alliance-empty-runtime__title">{t("emptyTitle")}</p>
          <p className="alliance-empty-runtime__detail">{t("emptyDetail")}</p>
        </div>
      ) : (
        <div className="alliance-panorama-grid">
          {sorted.map((a) => (
            <AlliancePanoramaCard alliance={a} key={a.id || a.name} />
          ))}
        </div>
      )}
    </OperationalModuleCard>
  );
}

export const AlliancePanoramaPanel = memo(AlliancePanoramaPanelInner);
