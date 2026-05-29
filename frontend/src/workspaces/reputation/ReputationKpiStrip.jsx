import React, { memo } from "react";
import { useTranslation } from "react-i18next";
import {
  Shield, TrendingDown, TrendingUp, AlertTriangle,
  Activity, BarChart3, Globe, Users, MessageSquare, FileText
} from "lucide-react";
import { formatScore } from "../../utils/formatMetric";

function ReputationKpiStripInner({ kpis }) {
  const { t } = useTranslation(["dashboard"]);
  if (!kpis) return null;

  const cards = [
    { icon: Users, key: "monitored", value: kpis.total, accent: "signal" },
    { icon: FileText, key: "totalReviews", value: kpis.totalReviews?.toLocaleString("pt-BR") ?? "—", accent: "signal" },
    { icon: Shield, key: "avgScore", value: formatScore(kpis.avgScore, { allowZero: true }), accent: kpis.avgScore >= 60 ? "positive" : "warning" },
    { icon: AlertTriangle, key: "critical", value: kpis.critical, accent: kpis.critical > 0 ? "risk" : "positive" },
    { icon: MessageSquare, key: "totalComplaints", value: kpis.totalComplaints?.toLocaleString("pt-BR") ?? "0", accent: kpis.totalComplaints > 0 ? "warning" : "positive" },
    { icon: TrendingDown, key: "deteriorating", value: kpis.deteriorating, accent: kpis.deteriorating > 0 ? "risk" : "positive" },
    { icon: TrendingUp, key: "recovering", value: kpis.recovering, accent: kpis.recovering > 0 ? "positive" : "neutral" },
    { icon: Activity, key: "emergingComplaints", value: kpis.emergingComplaints, accent: kpis.emergingComplaints > 0 ? "warning" : "positive" },
    { icon: BarChart3, key: "stability", value: `${kpis.avgStability}%`, accent: kpis.avgStability >= 60 ? "positive" : "warning" },
    { icon: Globe, key: "regionalRisk", value: kpis.worstRegion ? t(`dashboard:reputation.regions.${kpis.worstRegion.region}`) : "—", accent: "warning" },
  ];

  return (
    <section className="rep-kpi-strip">
      {cards.map(({ icon: Icon, key, value, accent }) => (
        <div className={`rep-kpi-card rep-kpi-card--${accent}`} key={key}>
          <div className="rep-kpi-icon"><Icon size={14} /></div>
          <div className="rep-kpi-body">
            <span className="rep-kpi-value metric-num">{value}</span>
            <span className="rep-kpi-label">{t(`dashboard:reputation.kpi.${key}`)}</span>
          </div>
        </div>
      ))}
    </section>
  );
}

export const ReputationKpiStrip = memo(ReputationKpiStripInner);
