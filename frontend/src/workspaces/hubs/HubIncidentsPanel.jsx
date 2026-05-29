import React, { memo } from "react";
import { useTranslation } from "react-i18next";
import { AlertTriangle, Clock } from "lucide-react";
import { OperationalModuleCard } from "../../components/forecasting/OperationalModuleCard";
import { SeverityBadge } from "../../components/ui/PanelShell";

function HubIncidentsPanelInner({ incidents, loading }) {
  const { t } = useTranslation("hubs");
  const rows = (incidents || []).slice(0, 20);
  const isEmpty = !loading && rows.length === 0;

  const status = (
    <span className="op-status-pill">
      <Clock size={12} aria-hidden />
      {rows.length || t("badgeRuntime")}
    </span>
  );

  return (
    <OperationalModuleCard
      className="hub-incidents-module"
      title={t("incidentsTitle")}
      subtitle={t("incidentsSubtitle")}
      status={status}
      expandable
      defaultExpanded={rows.length > 0}
      bodyClassName="hub-incidents-module__body"
    >
      {loading && isEmpty ? (
        <div className="hub-module-skeleton" />
      ) : isEmpty ? (
        <div className="hub-empty-runtime hub-empty-runtime--compact">
          <AlertTriangle size={18} strokeWidth={1.2} aria-hidden />
          <p className="hub-empty-runtime__title">{t("emptyHubTitle")}</p>
          <p className="hub-empty-runtime__detail">{t("emptyHubDetail")}</p>
        </div>
      ) : (
        <ul className="hub-incident-timeline intel-timeline" role="list">
          {rows.map((inc, i) => {
            const sev = (inc.severity || "medium").toLowerCase();
            return (
              <li
                className={`hub-incident-item timeline-item severity-${sev}`}
                key={`${inc.iata}-${inc.month}-${i}`}
                role="listitem"
              >
                <span className="timeline-marker" aria-hidden>
                  <AlertTriangle size={10} />
                </span>
                <div className="hub-incident-body">
                  <div className="timeline-head hub-incident-head">
                    <strong>
                      {inc.airport_name} ({inc.iata})
                    </strong>
                    <time>{inc.month}</time>
                  </div>
                  <p className="hub-incident-copy">
                    {t("incidentsComplaint", {
                      count: inc.complaint_count,
                      rating: inc.avg_rating,
                    })}
                  </p>
                  <div className="hub-incident-meta">
                    <SeverityBadge severity={sev} />
                    {(inc.top_complaints || []).map((c) => (
                      <span className="op-tag" key={c}>
                        {c}
                      </span>
                    ))}
                  </div>
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </OperationalModuleCard>
  );
}

export const HubIncidentsPanel = memo(HubIncidentsPanelInner);
