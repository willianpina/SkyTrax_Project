import React, { memo, useMemo } from "react";
import { useTranslation } from "react-i18next";
import { PanelShell, SeverityBadge } from "../ui/PanelShell";

function AnomalyFeedInner({ anomalies, alerts }) {
  const { t } = useTranslation(["command", "alerts", "common"]);

  const grouped = useMemo(() => {
    const combined = [
      ...(alerts || []).map((a) => ({ ...a, source: "alert" })),
      ...(anomalies || []).slice(0, 8).map((a) => ({ ...a, source: "anomaly" }))
    ].slice(0, 12);

    const groups = {};
    for (const item of combined) {
      const key = item.severity || "medium";
      if (!groups[key]) groups[key] = [];
      groups[key].push(item);
    }

    const order = ["critical", "high", "medium", "low"];
    return order
      .filter((s) => groups[s]?.length)
      .map((s) => ({ severity: s, items: groups[s] }));
  }, [anomalies, alerts]);

  const total = grouped.reduce((sum, g) => sum + g.items.length, 0);

  return (
    <PanelShell
      title={t("command:feed.anomalyTitle")}
      subtitle={t("command:feed.live", { count: total })}
      accent="risk"
      expandable
      defaultExpanded={total > 0}
      className="anomaly-feed-panel"
    >
      {total === 0 ? (
        <p className="muted-copy">{t("alerts:operationalAlerts.empty")}</p>
      ) : (
        <ul className="anomaly-feed">
          {grouped.map((group) => (
            <React.Fragment key={group.severity}>
              <li className="feed-group-header">
                <SeverityBadge severity={group.severity} />
                <span className="feed-group-count">{group.items.length}</span>
              </li>
              {group.items.map((row) => (
                <li className={`feed-card severity-${row.severity}`} key={`${row.source}-${row.id}`}>
                  <div className="feed-card-head">
                    <span className="feed-airline">{row.airline}</span>
                  </div>
                  <strong style={{ fontSize: "11px" }}>
                    {row.title || t(`alerts:types.${row.anomaly_type}`, { defaultValue: (row.anomaly_type || "").replace(/_/g, " ") })}
                  </strong>
                </li>
              ))}
            </React.Fragment>
          ))}
        </ul>
      )}
    </PanelShell>
  );
}

export const AnomalyFeed = memo(AnomalyFeedInner);
