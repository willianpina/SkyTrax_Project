import React, { memo, useCallback, useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { Shield } from "lucide-react";
import { OperationalModuleCard } from "../../components/forecasting/OperationalModuleCard";
import { flattenGroups, useGroupedAnomalies } from "./anomalyShared";
import { IncidentRow } from "./IncidentRow";

const BATCH_SIZE = 24;
const VIRTUAL_THRESHOLD = 20;

function AnomalyIncidentRuntimeInner({ anomalies }) {
  const { t } = useTranslation(["anomalies"]);
  const groups = useGroupedAnomalies(anomalies);
  const flat = useMemo(() => flattenGroups(groups), [groups]);
  const [renderLimit, setRenderLimit] = useState(BATCH_SIZE);

  useEffect(() => {
    setRenderLimit(flat.length > VIRTUAL_THRESHOLD ? BATCH_SIZE : flat.length);
  }, [flat.length, anomalies]);

  const visibleFlat = flat.slice(0, renderLimit);
  const hasMore = renderLimit < flat.length;

  const handleScroll = useCallback(
    (e) => {
      if (flat.length <= VIRTUAL_THRESHOLD) return;
      const el = e.currentTarget;
      if (el.scrollTop + el.clientHeight >= el.scrollHeight - 64 && hasMore) {
        setRenderLimit((n) => Math.min(n + BATCH_SIZE, flat.length));
      }
    },
    [flat.length, hasMore]
  );

  const visibleByGroup = useMemo(() => {
    const map = new Map();
    for (const item of visibleFlat) {
      const key = item.groupAirline;
      if (!map.has(key)) map.set(key, []);
      map.get(key).push(item);
    }
    return groups
      .filter((g) => map.has(g.airline))
      .map((g) => ({ ...g, items: map.get(g.airline) }));
  }, [groups, visibleFlat]);

  return (
    <OperationalModuleCard
      className="anomaly-incident-module"
      title={t("registry.runtimeTitle", { defaultValue: "Operational incident runtime" })}
      subtitle={t("registry.subtitle", {
        anomalies: flat.length,
        carriers: groups.length,
      })}
      meta={
        <span className="op-module-count">
          {visibleFlat.length}
          {flat.length > visibleFlat.length ? ` / ${flat.length}` : ""}
        </span>
      }
      status={
        flat.length > VIRTUAL_THRESHOLD ? (
          <span className="op-status-pill op-status-pill--muted">
            {t("registry.virtualHint", { defaultValue: "Progressive load · scroll for more" })}
          </span>
        ) : null
      }
      expandable
      defaultExpanded
      bodyClassName="anomaly-incident-module__body"
    >
      {groups.length === 0 ? (
        <div className="anm-empty-sm">
          <Shield size={20} strokeWidth={1.2} />
          <span>{t("registry.empty")}</span>
        </div>
      ) : (
        <div
          className="anomaly-incident-runtime-scroll"
          onScroll={handleScroll}
          role="region"
          aria-label={t("registry.runtimeTitle")}
        >
          {visibleByGroup.map((group) => (
            <section key={group.airline} className="anomaly-incident-group">
              <header className="anomaly-incident-group-head">
                <span className="anomaly-incident-group-name">{group.airline}</span>
                <span className="anomaly-incident-group-count">{group.items.length}</span>
              </header>
              <div className="anomaly-incident-group-body">
                {group.items.map((a) => (
                  <IncidentRow key={a.id} anomaly={a} compact />
                ))}
              </div>
            </section>
          ))}
          {hasMore ? (
            <p className="anomaly-incident-load-more muted-copy">
              {t("registry.loadingMore", {
                defaultValue: "Scroll to load more incidents…",
              })}
            </p>
          ) : null}
        </div>
      )}
    </OperationalModuleCard>
  );
}

export const AnomalyIncidentRuntime = memo(AnomalyIncidentRuntimeInner);
