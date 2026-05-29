import React, { memo } from "react";
import { useTranslation } from "react-i18next";
import { Globe, Network } from "lucide-react";
import { OperationalModuleCard } from "../../components/forecasting/OperationalModuleCard";
import { ALLIANCE_ORDER, sortAllianceHubs } from "./hubsShared";

const ALLIANCE_ACCENTS = {
  "Star Alliance": "#eab308",
  SkyTeam: "#3b82f6",
  Oneworld: "#ef4444",
};

function HubGlobalNetworkPanelInner({ hubAlliances, loading }) {
  const { t } = useTranslation("hubs");
  const alliances = sortAllianceHubs(hubAlliances);
  const isEmpty = !loading && alliances.length === 0;

  return (
    <OperationalModuleCard
      className="hub-network-module"
      title={t("networkTitle")}
      subtitle={t("networkSubtitle")}
      expandable
      defaultExpanded
      bodyClassName="hub-network-module__body"
    >
      {loading && isEmpty ? (
        <div className="hub-module-skeleton" />
      ) : isEmpty ? (
        <div className="hub-empty-runtime hub-empty-runtime--compact">
          <Network size={18} strokeWidth={1.2} aria-hidden />
          <p className="hub-empty-runtime__title">{t("emptyHubTitle")}</p>
          <p className="hub-empty-runtime__detail">{t("emptyHubDetail")}</p>
        </div>
      ) : (
        <div className="hub-network-grid">
          {ALLIANCE_ORDER.map((name) => {
            const alliance = alliances.find((a) => a.alliance_name === name);
            const accent = ALLIANCE_ACCENTS[name] || "#94a3b8";
            const hubs = (alliance?.hubs || []).slice(0, 8);
            return (
              <article
                className="hub-network-card"
                key={name}
                style={{ "--hub-alliance-accent": accent }}
              >
                <header className="hub-network-card__head">
                  <div className="hub-network-card__title">
                    <span className="hub-network-dot" aria-hidden />
                    <h3>{name}</h3>
                  </div>
                  {alliance ? (
                    <span className="hub-network-badge">
                      {t("networkRisks", { count: alliance.total_risk_mentions ?? 0 })}
                    </span>
                  ) : null}
                </header>
                {alliance ? (
                  <>
                    <p className="hub-network-summary">
                      {t("networkHubsSummary", {
                        count: alliance.hub_count ?? hubs.length,
                        rating: alliance.avg_rating ?? "—",
                      })}
                    </p>
                    <ul className="hub-network-list" role="list">
                      {hubs.map((h) => (
                        <li className="hub-network-hub" key={h.iata || h.airport_name} role="listitem">
                          <span className="hub-network-iata">{h.iata || "?"}</span>
                          <span className="hub-network-name">{h.airport_name}</span>
                          <span className="hub-network-country">{h.country}</span>
                          <span className="hub-network-stars" aria-hidden>
                            {"★".repeat(h.airport_rating || 0)}
                          </span>
                        </li>
                      ))}
                    </ul>
                  </>
                ) : (
                  <p className="hub-network-empty">
                    <Globe size={14} aria-hidden /> —
                  </p>
                )}
              </article>
            );
          })}
        </div>
      )}
    </OperationalModuleCard>
  );
}

export const HubGlobalNetworkPanel = memo(HubGlobalNetworkPanelInner);
