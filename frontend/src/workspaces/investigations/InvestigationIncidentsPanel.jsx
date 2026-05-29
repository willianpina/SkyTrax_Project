import React, { memo, useMemo } from "react";
import { useTranslation } from "react-i18next";
import { AlertTriangle } from "lucide-react";
import { OperationalModuleCard } from "../../components/forecasting/OperationalModuleCard";
import { SeverityBadge } from "../../components/ui/PanelShell";
import { formatOperationalDate } from "../../utils/datetime";
import { formatScore } from "../../utils/formatMetric";
import { filterByAirline, humanizeType, sortIncidentsBySeverity } from "./investigationsShared";

function InvestigationIncidentsPanelInner({ anomalies, selectedAirline, reputation }) {
  const { t } = useTranslation(["investigations", "anomalies"]);

  const rows = useMemo(() => {
    const filtered = filterByAirline(anomalies, selectedAirline, reputation);
    return sortIncidentsBySeverity(filtered).slice(0, 24);
  }, [anomalies, selectedAirline, reputation]);

  return (
    <OperationalModuleCard
      className="investigation-incidents-module"
      title={t("incidentsTitle")}
      subtitle={t("incidentsSubtitle")}
      expandable
      defaultExpanded
      bodyClassName="investigation-incidents-module__body"
    >
      {rows.length === 0 ? (
        <div className="investigation-empty-runtime">
          <AlertTriangle size={22} strokeWidth={1.2} aria-hidden />
          <p className="investigation-empty-runtime__title">{t("incidentsEmptyTitle")}</p>
          <p className="investigation-empty-runtime__detail">{t("incidentsEmptyDetail")}</p>
        </div>
      ) : (
        <ul className="investigation-incident-grid" role="list">
          {rows.map((a) => {
            const sev = (a.severity || "low").toLowerCase();
            const typeName = humanizeType(a.anomaly_type);
            const sevLabel = t(`anomalies:severity.${sev}`, { defaultValue: sev });

            return (
              <li
                className={`investigation-incident-card insight-signal-card severity-${sev}`}
                key={a.id ?? `${a.airline}-${a.detected_at}-${typeName}`}
                role="listitem"
              >
                <div className="investigation-incident-head">
                  <SeverityBadge severity={sev} label={sevLabel} />
                  <time className="investigation-incident-time" dateTime={a.detected_at || undefined}>
                    {formatOperationalDate(a.detected_at)}
                  </time>
                </div>
                <strong className="investigation-incident-airline">{a.airline || "—"}</strong>
                <p className="investigation-incident-type">{typeName}</p>
                <p className="investigation-incident-metric">
                  {t("metricVs", {
                    observed: formatScore(a.observed_value, { allowZero: true }),
                    expected: formatScore(a.expected_value, { allowZero: true }),
                  })}
                </p>
              </li>
            );
          })}
        </ul>
      )}
    </OperationalModuleCard>
  );
}

export const InvestigationIncidentsPanel = memo(InvestigationIncidentsPanelInner);
