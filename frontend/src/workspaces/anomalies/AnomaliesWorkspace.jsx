import React, { useMemo, useState, memo } from "react";
import { useTranslation } from "react-i18next";
import { useSharedAnalytics } from "../../hooks/AnalyticsProvider";
import { WorkspaceShell } from "../../layouts/WorkspaceShell";
import { PanelShell, SeverityBadge } from "../../components/ui/PanelShell";
import { OperationalBadge } from "../../components/ui/OperationalBadge";
import { AnomalyTimeline } from "../../components/AnomalyPanel";
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
  const kpis = [
    { icon: AlertTriangle, label: "Active Signals", value: total, sub: "Monitored anomaly events", accent: "risk" },
    { icon: Zap, label: "Critical", value: counts.critical + counts.high, sub: "Requiring immediate action", accent: counts.critical + counts.high > 0 ? "risk" : "signal" },
    { icon: Activity, label: "Medium", value: counts.medium, sub: "Under observation", accent: counts.medium > 0 ? "warning" : "signal" },
    { icon: Radio, label: "Low Priority", value: counts.low, sub: "Informational signals", accent: "signal" },
    { icon: Shield, label: "Carriers Affected", value: 0, sub: "Distinct airlines flagged", accent: "signal" },
    { icon: BarChart3, label: "Detection Coverage", value: "—", sub: "Operational confidence", accent: "signal" },
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
              {group.severities[s]} {s}
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

const IncidentRow = memo(function IncidentRow({ anomaly: a }) {
  const sev = a.severity || "low";
  const typeName = (a.anomaly_type || "").replace(/_/g, " ");

  return (
    <div className={`anm-incident anm-incident--${sev}`}>
      <div className="anm-incident-sev">
        <OperationalBadge variant={SEV_CONFIG[sev]?.variant || "neutral"} compact>{sev}</OperationalBadge>
      </div>
      <div className="anm-incident-body">
        <span className="anm-incident-type">{typeName}</span>
        <span className="anm-incident-metric">
          {a.metric}: <strong>{a.observed_value}</strong> vs expected <strong>{a.expected_value}</strong>
        </span>
      </div>
      <time className="anm-incident-time">{a.detected_at?.slice(0, 10)}</time>
    </div>
  );
});

function SignalStream({ anomalies, alerts }) {
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
      <PanelShell title="Signal Stream" subtitle="No active signals" accent="signal">
        <div className="anm-empty-sm">
          <Radio size={18} strokeWidth={1.2} />
          <span>No anomaly signals detected in the current window</span>
        </div>
      </PanelShell>
    );
  }

  return (
    <PanelShell title="Live Signal Stream" subtitle={`${combined.length} latest detections`} accent="risk" expandable>
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
              <time className="anm-signal-time">{s.detected_at?.slice(0, 10)}</time>
            </div>
          );
        })}
      </div>
    </PanelShell>
  );
}

function ExecutiveAssessment({ anomalies }) {
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
      msgs.push({ sev: "high", text: `${criticalAirlines.length} carrier(s) with critical escalation signals: ${criticalAirlines.slice(0, 3).join(", ")}${criticalAirlines.length > 3 ? "…" : ""}` });
    }
    if (sevCounts.medium > 3) {
      msgs.push({ sev: "medium", text: `${sevCounts.medium} medium-priority anomalies detected — emerging deterioration patterns under observation` });
    }
    if (sevCounts.low > 0) {
      msgs.push({ sev: "low", text: `${sevCounts.low} informational signals tracked — operational baseline monitoring active` });
    }
    if (msgs.length === 0) {
      msgs.push({ sev: "low", text: "All carriers within operational baselines. No escalation required." });
    }
    return msgs;
  }, [anomalies]);

  return (
    <PanelShell title="Executive Assessment" subtitle="Operational posture summary" accent="signal" expandable>
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
  const { t } = useTranslation(["alerts", "command", "common", "nav"]);
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
      subtitle={`${totalSignals} active signals monitored`}
      accent="risk"
    >
      <SeverityStrip counts={counts} total={totalSignals} />

      {/* Severity filter bar */}
      <div className="anm-filter-bar">
        <button
          type="button"
          className={`anm-filter-btn ${!sevFilter ? "anm-filter--active" : ""}`}
          onClick={() => setSevFilter(null)}
        >All</button>
        {SEV_ORDER.map((s) => (
          <button
            key={s}
            type="button"
            className={`anm-filter-btn anm-filter-btn--${s} ${sevFilter === s ? "anm-filter--active" : ""}`}
            onClick={() => setSevFilter(sevFilter === s ? null : s)}
          >{s} ({counts[s]})</button>
        ))}
      </div>

      <div className="anm-layout">
        <div className="anm-main">
          <AnomalyTimeline anomalies={anomalies} />

          <PanelShell
            title="Incident Registry"
            subtitle={`${filtered.length} anomalies · ${groups.length} carriers`}
            accent="risk"
            expandable
          >
            {groups.length === 0 ? (
              <div className="anm-empty-sm">
                <Shield size={20} strokeWidth={1.2} />
                <span>No anomalies detected. Operational baselines stable.</span>
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
