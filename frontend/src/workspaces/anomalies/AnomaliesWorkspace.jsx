import React, { useMemo, useState, memo } from "react";
import { useTranslation } from "react-i18next";
import { useSharedAnalytics } from "../../hooks/AnalyticsProvider";
import { WorkspaceShell } from "../../layouts/WorkspaceShell";
import { PanelShell, SeverityBadge } from "../../components/ui/PanelShell";
import { OperationalBadge } from "../../components/ui/OperationalBadge";
import { AnomalyTimeline } from "../../components/AnomalyPanel";
import { formatShortDate } from "../../utils/datetime";
import { formatScore, formatGap as fmtGap } from "../../utils/formatMetric";
import {
  AlertTriangle, Shield, Radio, TrendingDown,
  BarChart3, Activity, ChevronDown, ChevronRight,
  Zap, Clock,
} from "lucide-react";

const SEV_ORDER = ["critical", "high", "medium", "low"];
const SEV_CONFIG = {
  critical: { variant: "danger", icon: Zap, label: "Critical" },
  high: { variant: "danger", icon: AlertTriangle, label: "High" },
  medium: { variant: "warning", icon: Activity, label: "Medium" },
  low: { variant: "info", icon: Radio, label: "Low" },
};

function SeverityStrip({ counts, total }) {
  const { t } = useTranslation(["anomalies"]);
  const kpis = [
    { icon: AlertTriangle, label: t("anomalies:strip.activeSignals"), value: total, sub: t("anomalies:strip.activeSignalsSub"), accent: "risk" },
    { icon: Zap, label: t("anomalies:strip.critical"), value: counts.critical + counts.high, sub: t("anomalies:strip.criticalSub"), accent: counts.critical + counts.high > 0 ? "risk" : "signal" },
    { icon: Activity, label: t("anomalies:strip.medium"), value: counts.medium, sub: t("anomalies:strip.mediumSub"), accent: counts.medium > 0 ? "warning" : "signal" },
    { icon: Radio, label: t("anomalies:strip.lowPriority"), value: counts.low, sub: t("anomalies:strip.lowPrioritySub"), accent: "signal" },
    { icon: Shield, label: t("anomalies:strip.carriers"), value: 0, sub: t("anomalies:strip.carriersSub"), accent: "signal" },
    { icon: BarChart3, label: t("anomalies:strip.detection"), value: "—", sub: t("anomalies:strip.detectionSub"), accent: "signal" },
  ];

  return (
    <section className="anm-kpi-strip">
      {kpis.map(({ icon: Icon, label, value, sub, accent }) => (
        <div className={`anm-kpi glass-panel ${accent === "risk" && value > 0 ? "anm-kpi--alert" : ""}`} key={label}>
          <div className="anm-kpi-top">
            <span className="anm-kpi-icon"><Icon size={13} /></span>
            <span className="anm-kpi-label">{label}</span>
          </div>
          <span className="anm-kpi-value">{value}</span>
          <span className="anm-kpi-sub">{sub}</span>
        </div>
      ))}
    </section>
  );
}

function useGroupedAnomalies(anomalies) {
  return useMemo(() => {
    const byAirline = {};
    for (const a of anomalies || []) {
      const key = a.airline || "Unknown";
      if (!byAirline[key]) byAirline[key] = { airline: key, items: [], severities: {} };
      byAirline[key].items.push(a);
      const sev = a.severity || "low";
      byAirline[key].severities[sev] = (byAirline[key].severities[sev] || 0) + 1;
    }

    const groups = Object.values(byAirline);
    groups.sort((a, b) => {
      const aScore = (a.severities.critical || 0) * 100 + (a.severities.high || 0) * 10 + (a.severities.medium || 0);
      const bScore = (b.severities.critical || 0) * 100 + (b.severities.high || 0) * 10 + (b.severities.medium || 0);
      return bScore - aScore;
    });
    return groups;
  }, [anomalies]);
}

const AirlineGroup = memo(function AirlineGroup({ group }) {
  const { t } = useTranslation(["anomalies"]);
  const [open, setOpen] = useState(group.severities.critical > 0 || group.severities.high > 0);
  const maxSev = SEV_ORDER.find((s) => group.severities[s] > 0) || "low";
  const conf = SEV_CONFIG[maxSev];

  return (
    <div className={`anm-group ${open ? "anm-group--open" : ""}`}>
      <button type="button" className="anm-group-header" onClick={() => setOpen((o) => !o)}>
        <span className="anm-group-chevron">{open ? <ChevronDown size={13} /> : <ChevronRight size={13} />}</span>
        <span className="anm-group-name">{group.airline}</span>
        <span className="anm-group-badges">
          {SEV_ORDER.filter((s) => group.severities[s] > 0).map((s) => (
            <OperationalBadge key={s} variant={SEV_CONFIG[s].variant} compact>
              {group.severities[s]} {t(`anomalies:filter.${s}`)}
            </OperationalBadge>
          ))}
        </span>
        <span className="anm-group-total">{group.items.length}</span>
      </button>
      {open && (
        <div className="anm-group-body">
          {group.items.map((a) => (
            <IncidentRow key={a.id} anomaly={a} />
          ))}
        </div>
      )}
    </div>
  );
});

function categorizeAnomaly(type) {
  const s = (type || "").toLowerCase();
  if (s.includes("reputation") || s.includes("score")) return "reputation";
  if (s.includes("sentiment") || s.includes("rating")) return "sentiment";
  if (s.includes("complaint") || s.includes("density")) return "complaints";
  if (s.includes("service") || s.includes("crew") || s.includes("cabin")) return "service";
  if (s.includes("delay") || s.includes("cancel")) return "operations";
  return "signal";
}

function formatGap(observed, expected) {
  return fmtGap(observed, expected);
}

const IncidentRow = memo(function IncidentRow({ anomaly: a }) {
  const { t } = useTranslation(["anomalies"]);
  const sev = a.severity || "low";
  const typeName = (a.anomaly_type || "").replace(/_/g, " ");
  const categoryKey = categorizeAnomaly(a.anomaly_type);
  const category = t(`anomalies:categories.${categoryKey}`);
  const gap = formatGap(a.observed_value, a.expected_value);
  const sevLabel = t(`anomalies:severity.${sev}`);

  return (
    <div className={`anm-incident anm-incident--${sev}`}>
      <div className="anm-incident-lead">
        <span className={`anm-sev-dot anm-sev-dot--${sev}`} />
        <span className={`anm-sev-chip anm-sev-chip--${sev}`}>{sevLabel}</span>
      </div>
      <div className="anm-incident-primary">
        <span className="anm-incident-type">{typeName}</span>
        <span className="anm-incident-cat">{category}</span>
      </div>
      <div className="anm-incident-scores">
        <div className="anm-score-cell">
          <span className="anm-score-label">{t("anomalies:registry.observed")}</span>
          <span className="anm-score-val metric-num">{formatScore(a.observed_value, { allowZero: true })}</span>
        </div>
        <div className="anm-score-cell">
          <span className="anm-score-label">{t("anomalies:registry.threshold")}</span>
          <span className="anm-score-val anm-score-val--dim metric-num">{formatScore(a.expected_value, { allowZero: true })}</span>
        </div>
        {gap && (
          <div className="anm-score-cell">
            <span className="anm-score-label">{t("anomalies:registry.gap")}</span>
            <span className={`anm-score-val anm-score-gap ${parseFloat(gap) < 0 ? "anm-score-gap--neg" : "anm-score-gap--pos"}`}>{gap}</span>
          </div>
        )}
      </div>
      <time className="anm-incident-time">{formatShortDate(a.detected_at)}</time>
    </div>
  );
});

function SignalStream({ anomalies, alerts }) {
  const { t } = useTranslation(["anomalies"]);
  const combined = useMemo(() => {
    const all = [
      ...(alerts || []).map((a) => ({ ...a, _src: "alert" })),
      ...(anomalies || []).slice(0, 12).map((a) => ({ ...a, _src: "anomaly" })),
    ];
    all.sort((a, b) => (b.detected_at || "").localeCompare(a.detected_at || ""));
    return all.slice(0, 10);
  }, [anomalies, alerts]);

  if (combined.length === 0) {
    return (
      <PanelShell title={t("anomalies:stream.emptyTitle")} subtitle={t("anomalies:stream.emptySub")} accent="signal">
        <div className="anm-empty-sm">
          <Radio size={18} strokeWidth={1.2} />
          <span>{t("anomalies:stream.emptyMsg")}</span>
        </div>
      </PanelShell>
    );
  }

  return (
    <PanelShell title={t("anomalies:stream.title")} subtitle={t("anomalies:stream.subtitle", { count: combined.length })} accent="risk" expandable>
      <div className="anm-stream">
        {combined.map((s, i) => {
          const sev = s.severity || "low";
          const conf = SEV_CONFIG[sev] || SEV_CONFIG.low;
          const Icon = conf.icon;
          return (
            <div className={`anm-signal anm-signal--${sev}`} key={`${s._src}-${s.id}-${i}`}>
              <span className="anm-signal-icon"><Icon size={12} /></span>
              <div className="anm-signal-body">
                <span className="anm-signal-airline">{s.airline}</span>
                <span className="anm-signal-type">
                  {s.title || (s.anomaly_type || "").replace(/_/g, " ")}
                </span>
              </div>
              <time className="anm-signal-time">{formatShortDate(s.detected_at)}</time>
            </div>
          );
        })}
      </div>
    </PanelShell>
  );
}

function ExecutiveAssessment({ anomalies }) {
  const { t } = useTranslation(["anomalies"]);
  const insights = useMemo(() => {
    if (!anomalies || anomalies.length === 0) return [];
    const sevCounts = { critical: 0, high: 0, medium: 0, low: 0 };
    const airlineSevs = {};
    for (const a of anomalies) {
      sevCounts[a.severity] = (sevCounts[a.severity] || 0) + 1;
      if (!airlineSevs[a.airline]) airlineSevs[a.airline] = [];
      airlineSevs[a.airline].push(a.severity);
    }

    const msgs = [];
    const criticalAirlines = Object.entries(airlineSevs)
      .filter(([, sevs]) => sevs.includes("critical") || sevs.includes("high"))
      .map(([name]) => name);

    if (criticalAirlines.length > 0) {
      msgs.push({ sev: "high", text: t("anomalies:assessment.criticalEscalation", { count: criticalAirlines.length, airlines: criticalAirlines.slice(0, 3).join(", ") + (criticalAirlines.length > 3 ? "…" : "") }) });
    }
    if (sevCounts.medium > 3) {
      msgs.push({ sev: "medium", text: t("anomalies:assessment.mediumDetected", { count: sevCounts.medium }) });
    }
    if (sevCounts.low > 0) {
      msgs.push({ sev: "low", text: t("anomalies:assessment.lowTracked", { count: sevCounts.low }) });
    }
    if (msgs.length === 0) {
      msgs.push({ sev: "low", text: t("anomalies:assessment.allStable") });
    }
    return msgs;
  }, [anomalies, t]);

  return (
    <PanelShell title={t("anomalies:assessment.title")} subtitle={t("anomalies:assessment.subtitle")} accent="signal" expandable>
      <div className="anm-assessment">
        {insights.map((ins, i) => (
          <div className={`anm-assess-row anm-assess--${ins.sev}`} key={i}>
            <span className="anm-assess-dot" />
            <span className="anm-assess-text">{ins.text}</span>
          </div>
        ))}
      </div>
    </PanelShell>
  );
}

export default function AnomaliesWorkspace() {
  const { t } = useTranslation(["anomalies", "alerts", "command", "common", "nav"]);
  const { anomalies, alerts } = useSharedAnalytics();
  const [sevFilter, setSevFilter] = useState(null);

  const counts = useMemo(() => {
    const c = { critical: 0, high: 0, medium: 0, low: 0 };
    for (const a of anomalies || []) c[a.severity] = (c[a.severity] || 0) + 1;
    for (const a of alerts || []) c[a.severity] = (c[a.severity] || 0) + 1;
    return c;
  }, [anomalies, alerts]);

  const totalSignals = (anomalies?.length || 0) + (alerts?.length || 0);

  const filtered = useMemo(() => {
    if (!sevFilter) return anomalies || [];
    return (anomalies || []).filter((a) => a.severity === sevFilter);
  }, [anomalies, sevFilter]);

  const groups = useGroupedAnomalies(filtered);

  // Update carriers affected in KPI strip
  const carriersAffected = useMemo(() => {
    const set = new Set();
    for (const a of anomalies || []) if (a.airline) set.add(a.airline);
    for (const a of alerts || []) if (a.airline) set.add(a.airline);
    return set.size;
  }, [anomalies, alerts]);

  return (
    <WorkspaceShell
      id="anomalies"
      title={t("nav:nav.anomalies")}
      subtitle={t("anomalies:subtitle", { count: totalSignals })}
      accent="risk"
    >
      <SeverityStrip counts={counts} total={totalSignals} />

      {/* Severity filter bar */}
      <div className="anm-filter-bar">
        <button
          type="button"
          className={`anm-filter-btn ${!sevFilter ? "anm-filter--active" : ""}`}
          onClick={() => setSevFilter(null)}
        >{t("anomalies:filter.all")}</button>
        {SEV_ORDER.map((s) => (
          <button
            key={s}
            type="button"
            className={`anm-filter-btn anm-filter-btn--${s} ${sevFilter === s ? "anm-filter--active" : ""}`}
            onClick={() => setSevFilter(sevFilter === s ? null : s)}
          >{t(`anomalies:filter.${s}`)} ({counts[s]})</button>
        ))}
      </div>

      <div className="anm-layout">
        <div className="anm-main">
          <AnomalyTimeline anomalies={anomalies} />

          <PanelShell
            title={t("anomalies:registry.title")}
            subtitle={t("anomalies:registry.subtitle", { anomalies: filtered.length, carriers: groups.length })}
            accent="risk"
            expandable
          >
            {groups.length === 0 ? (
              <div className="anm-empty-sm">
                <Shield size={20} strokeWidth={1.2} />
                <span>{t("anomalies:registry.empty")}</span>
              </div>
            ) : (
              <div className="anm-groups">
                {groups.map((g) => (
                  <AirlineGroup key={g.airline} group={g} />
                ))}
              </div>
            )}
          </PanelShell>

          <ExecutiveAssessment anomalies={anomalies} />
        </div>

        <aside className="anm-aside">
          <SignalStream anomalies={anomalies} alerts={alerts} />
        </aside>
      </div>
    </WorkspaceShell>
  );
}
