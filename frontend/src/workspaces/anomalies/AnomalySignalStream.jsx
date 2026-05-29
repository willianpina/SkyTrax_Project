import React, { memo, useMemo } from "react";
import { useTranslation } from "react-i18next";
import { AlertTriangle, Activity, Radio, Zap } from "lucide-react";
import { OperationalModuleCard } from "../../components/forecasting/OperationalModuleCard";
import { SeverityBadge } from "../../components/ui/PanelShell";
import { formatOperationalDate } from "../../utils/datetime";
import { categorizeAnomaly } from "./anomalyShared";

const ICONS = { critical: Zap, high: AlertTriangle, medium: Activity, low: Radio };

function humanizeType(type) {
  if (!type) return "";
  return type.replace(/_/g, " ");
}

function signalTitle(item) {
  if (item.title) return item.title;
  return humanizeType(item.anomaly_type) || "—";
}

function signalDescription(item, t) {
  if (item.detail) return item.detail;
  if (item.summary) return item.summary;
  const categoryKey = categorizeAnomaly(item.anomaly_type);
  const category = t(`categories.${categoryKey}`);
  if (item.observed_value != null && item.expected_value != null) {
    return `${category} · ${item.metric || humanizeType(item.anomaly_type)}`;
  }
  return category;
}

function AnomalySignalStreamInner({ anomalies, alerts }) {
  const { t } = useTranslation(["anomalies", "alerts"]);

  const combined = useMemo(() => {
    const all = [
      ...(alerts || []).map((a) => ({ ...a, _src: "alert" })),
      ...(anomalies || []).map((a) => ({ ...a, _src: "anomaly" })),
    ];
    all.sort((a, b) => (b.detected_at || "").localeCompare(a.detected_at || ""));
    return all.slice(0, 12);
  }, [anomalies, alerts]);

  return (
    <OperationalModuleCard
      className="anomaly-stream-module"
      title={t("stream.title")}
      subtitle={
        combined.length
          ? t("stream.subtitle", { count: combined.length })
          : t("stream.emptySub")
      }
      expandable
      defaultExpanded={combined.length > 0}
      bodyClassName="anomaly-stream-module__body"
    >
      {combined.length === 0 ? (
        <div className="ops-signal-feed-empty">
          <Radio size={18} strokeWidth={1.2} aria-hidden />
          <span>{t("stream.emptyMsg")}</span>
        </div>
      ) : (
        <ul className="ops-signal-feed ops-signal-feed--runtime" role="list">
          {combined.map((s, i) => {
            const sev = (s.severity || "low").toLowerCase();
            const Icon = ICONS[sev] || Radio;
            const title = signalTitle(s);
            const desc = signalDescription(s, t);

            return (
              <li
                className={`ops-signal-feed-item severity-${sev}`}
                key={`${s._src}-${s.id ?? s.airline}-${s.detected_at}-${i}`}
                role="listitem"
              >
                <span className="ops-signal-feed-icon" aria-hidden>
                  <Icon size={14} strokeWidth={1.75} />
                </span>
                <div className="ops-signal-feed-body">
                  <strong className="ops-signal-feed-title">{title}</strong>
                  {desc ? <p className="ops-signal-feed-desc">{desc}</p> : null}
                  <div className="ops-signal-feed-meta">
                    <SeverityBadge severity={sev} label={t(`severity.${sev}`, { defaultValue: sev })} />
                    <span className="ops-signal-feed-meta-sep" aria-hidden>
                      •
                    </span>
                    <time className="ops-signal-feed-time" dateTime={s.detected_at || undefined}>
                      {formatOperationalDate(s.detected_at)}
                    </time>
                  </div>
                </div>
                <div className="ops-signal-feed-airline">{s.airline || "—"}</div>
              </li>
            );
          })}
        </ul>
      )}
    </OperationalModuleCard>
  );
}

export const AnomalySignalStream = memo(AnomalySignalStreamInner);
