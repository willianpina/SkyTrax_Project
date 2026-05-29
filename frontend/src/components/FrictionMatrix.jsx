import React, { memo, useState, useEffect, useCallback, useMemo, Suspense, lazy } from "react";
import { useTranslation } from "react-i18next";
import {
  X, TrendingUp, TrendingDown, Minus, AlertTriangle,
  BarChart3, Activity, Flame, ChevronRight, Clock, MapPin,
} from "lucide-react";
import { fetchJson } from "../lib/apiClient";
import { PanelShell } from "./ui/PanelShell";
import { baseChartTheme, PALANTIR_COLORS } from "../lib/chartTheme";
import { formatShortDate } from "../utils/datetime";

const ReactECharts = lazy(() =>
  import("echarts-for-react").then((m) => ({ default: m.default ?? m }))
);

/* ── Color scale ────────────────────────────────────────────── */
const FRICTION_COLORS = [
  "#0f1923", "#13263a", "#1a3655", "#1e5080",
  "#c9a832", "#d4912a", "#cc6633", "#c95545", "#e05040",
];

function scoreColor(score, maxScore) {
  if (score <= 0) return FRICTION_COLORS[0];
  const ratio = Math.min(score / Math.max(maxScore, 1), 1);
  const idx = Math.min(Math.floor(ratio * (FRICTION_COLORS.length - 1)), FRICTION_COLORS.length - 1);
  return FRICTION_COLORS[idx];
}

function severityLabel(score) {
  if (score >= 70) return "critical";
  if (score >= 50) return "high";
  if (score >= 30) return "elevated";
  if (score >= 15) return "moderate";
  if (score > 0) return "low";
  return "none";
}

function TrendIcon({ dir }) {
  if (dir === "worsening") return <TrendingUp size={10} className="fm-trend fm-trend--worse" />;
  if (dir === "improving") return <TrendingDown size={10} className="fm-trend fm-trend--better" />;
  return <Minus size={10} className="fm-trend fm-trend--stable" />;
}

/* ── Tooltip formatter ──────────────────────────────────────── */
function buildTooltipContent(cell) {
  if (!cell || cell.score === 0) return null;
  const trendArrow = cell.trend_dir === "worsening" ? "↑" : cell.trend_dir === "improving" ? "↓" : "→";
  const trendColor = cell.trend_dir === "worsening" ? "#e05040" : cell.trend_dir === "improving" ? "#2dd4a8" : "#64748b";
  return `
    <div style="min-width:200px;font-family:Inter,system-ui,sans-serif;font-size:11px;line-height:1.5">
      <div style="font-weight:700;margin-bottom:4px;color:#e2e8f0">${cell.airline_name}</div>
      <div style="font-size:10px;color:#94a3b8;margin-bottom:6px">${cell.cluster_label}</div>
      <div style="display:flex;align-items:baseline;gap:6px;margin-bottom:6px">
        <span style="font-size:18px;font-weight:800;color:${scoreColor(cell.score, 80)}">${cell.score}</span>
        <span style="font-size:9px;color:#64748b">FRICTION SCORE</span>
      </div>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:2px 12px;font-size:10px">
        <span style="color:#94a3b8">Neg. sentiment</span><span style="color:#e05040;font-weight:600">${cell.neg_pct}%</span>
        <span style="color:#94a3b8">Reviews</span><span style="font-weight:600">${cell.count}</span>
        <span style="color:#94a3b8">Last 30d</span><span style="font-weight:600">${cell.recent_30d}</span>
        <span style="color:#94a3b8">Trend</span><span style="color:${trendColor};font-weight:600">${trendArrow} ${Math.abs(cell.trend_pct)}%</span>
        ${cell.avg_rating != null ? `<span style="color:#94a3b8">Avg rating</span><span style="font-weight:600">${cell.avg_rating}</span>` : ""}
      </div>
    </div>
  `;
}

/* ── ECharts heatmap option builder ─────────────────────────── */
function buildFrictionHeatmapOption(data) {
  if (!data || !data.airlines?.length) return null;

  const yLabels = data.airlines.map((a) => a.name);
  const xLabels = data.clusters;
  const maxScore = data.max_score || 80;

  const heatData = [];
  const cellIndex = {};
  (data.matrix || []).forEach((row, yi) => {
    (row || []).forEach((cell, xi) => {
      heatData.push([xi, yi, cell.score || 0]);
      cellIndex[`${xi}-${yi}`] = cell;
    });
  });

  return {
    ...baseChartTheme({
      grid: { left: 120, right: 40, top: 20, bottom: 80 },
    }),
    tooltip: {
      trigger: "item",
      backgroundColor: "rgba(10, 16, 24, 0.96)",
      borderColor: "#1e2d3d",
      borderWidth: 1,
      padding: 10,
      extraCssText: "backdrop-filter:blur(8px);box-shadow:0 4px 20px rgba(0,0,0,0.5);border-radius:6px;",
      formatter: (params) => {
        const [x, y] = params.data || [];
        const cell = cellIndex[`${x}-${y}`];
        return buildTooltipContent(cell);
      },
    },
    xAxis: {
      type: "category",
      data: xLabels,
      axisLabel: { color: "#7a8fa0", fontSize: 8, rotate: 35, interval: 0 },
      axisLine: { lineStyle: { color: "#1e2d3d" } },
      splitLine: { show: false },
    },
    yAxis: {
      type: "category",
      data: yLabels,
      axisLabel: { color: "#8fa0b0", fontSize: 9, width: 100, overflow: "truncate" },
      axisLine: { lineStyle: { color: "#1e2d3d" } },
      splitLine: { show: false },
    },
    visualMap: {
      min: 0,
      max: maxScore,
      show: true,
      orient: "horizontal",
      left: "center",
      bottom: 2,
      itemWidth: 12,
      itemHeight: 100,
      textStyle: { color: "#64748b", fontSize: 8 },
      text: ["Critical", "Low"],
      inRange: {
        color: FRICTION_COLORS,
      },
    },
    series: [
      {
        type: "heatmap",
        data: heatData,
        label: {
          show: true,
          fontSize: 8,
          fontWeight: 600,
          color: "#c0cdd8",
          formatter: (p) => (p.data[2] > 0 ? p.data[2] : ""),
        },
        emphasis: {
          itemStyle: { borderColor: "#3d9eff", borderWidth: 2 },
        },
        itemStyle: { borderColor: "#0d1520", borderWidth: 1, borderRadius: 2 },
      },
    ],
    _cellIndex: cellIndex,
  };
}

/* ── MetricsBadges ──────────────────────────────────────────── */
function MetricsBadges({ metrics }) {
  if (!metrics) return null;
  const { global_friction, hottest_clusters = [], riskiest_airlines = [] } = metrics;
  return (
    <div className="fm-badges">
      <span className="fm-badge fm-badge--friction">
        <Flame size={10} />
        <span>Global Friction</span>
        <strong>{global_friction}</strong>
      </span>
      {hottest_clusters[0] && (
        <span className="fm-badge fm-badge--hot">
          <AlertTriangle size={10} />
          <span>Hottest</span>
          <strong>{hottest_clusters[0].cluster_id?.replace(/_/g, " ")}</strong>
        </span>
      )}
      {riskiest_airlines[0] && (
        <span className="fm-badge fm-badge--risk">
          <Activity size={10} />
          <span>Riskiest</span>
          <strong>{riskiest_airlines[0].slug}</strong>
        </span>
      )}
    </div>
  );
}

/* ── Drilldown Panel ────────────────────────────────────────── */
function DrilldownPanel({ cell, onClose }) {
  const [detail, setDetail] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!cell) return;
    setLoading(true);
    fetchJson(`/intelligence/friction-matrix/drilldown?airline=${cell.airline_slug}&cluster=${cell.cluster_id}&limit=30`, null)
      .then((d) => { setDetail(d); setLoading(false); })
      .catch(() => setLoading(false));
  }, [cell]);

  if (!cell) return null;
  const sev = severityLabel(cell.score);

  return (
    <div className="fm-drill-overlay" onClick={onClose}>
      <div className="fm-drill glass-panel" onClick={(e) => e.stopPropagation()}>
        <div className="fm-drill-header">
          <div>
            <h3>{cell.airline_name}</h3>
            <span className="fm-drill-cluster">{cell.cluster_label}</span>
          </div>
          <div className="fm-drill-right">
            <span className={`fm-sev fm-sev--${sev}`}>{sev}</span>
            <button type="button" className="osm-close" onClick={onClose} aria-label="Close"><X size={14} /></button>
          </div>
        </div>

        <div className="fm-drill-kpis">
          <div className="fm-dk"><span className="fm-dk-val">{cell.score}</span><span className="fm-dk-lbl">Friction</span></div>
          <div className="fm-dk"><span className="fm-dk-val">{cell.neg_pct}%</span><span className="fm-dk-lbl">Negative</span></div>
          <div className="fm-dk"><span className="fm-dk-val">{cell.count}</span><span className="fm-dk-lbl">Reviews</span></div>
          <div className="fm-dk"><span className="fm-dk-val">{cell.recent_30d}</span><span className="fm-dk-lbl">Last 30d</span></div>
          <div className="fm-dk">
            <span className="fm-dk-val"><TrendIcon dir={cell.trend_dir} /> {Math.abs(cell.trend_pct)}%</span>
            <span className="fm-dk-lbl">Trend</span>
          </div>
        </div>

        {loading && <div className="fm-drill-loading"><div className="osm-shimmer" style={{ width: "100%", height: 12 }} /></div>}

        {detail && !loading && (
          <>
            {detail.timeline?.length > 0 && (
              <div className="fm-drill-timeline">
                <h4><Clock size={11} /> Monthly Volume</h4>
                <div className="fm-tl-bars">
                  {detail.timeline.map((t) => (
                    <div className="fm-tl-bar" key={t.month}>
                      <div className="fm-tl-fill" style={{ height: `${Math.min(100, (t.count / Math.max(...detail.timeline.map((x) => x.count), 1)) * 100)}%` }} />
                      <span className="fm-tl-label">{t.month.slice(5)}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {detail.top_routes?.length > 0 && (
              <div className="fm-drill-routes">
                <h4><MapPin size={11} /> Affected Routes</h4>
                <div className="fm-route-list">
                  {detail.top_routes.map((r) => (
                    <span className="fm-route-tag" key={r.route}>{r.route} <em>({r.count})</em></span>
                  ))}
                </div>
              </div>
            )}

            {detail.reviews?.length > 0 && (
              <div className="fm-drill-reviews">
                <h4>Related Reviews ({detail.total_matched})</h4>
                <div className="fm-review-list">
                  {detail.reviews.map((rv) => (
                    <div className="fm-review" key={rv.id}>
                      <div className="fm-review-head">
                        <span className={`fm-sent fm-sent--${rv.sentiment || "neutral"}`}>{rv.sentiment || "—"}</span>
                        {rv.rating != null && <span className="fm-review-rating">{rv.rating}/10</span>}
                        {rv.date && <span className="fm-review-date">{formatShortDate(rv.date)}</span>}
                        {rv.route && <span className="fm-review-route">{rv.route}</span>}
                      </div>
                      <p className="fm-review-text">{rv.title ? <strong>{rv.title}.</strong> : null} {rv.text}</p>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}

/* ── Main Component ─────────────────────────────────────────── */
function FrictionMatrixInner({ bare = false, chartMaxHeight = null, className = "", emptyContent = null }) {
  const { t } = useTranslation(["semantic", "benchmarking"]);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [selectedCell, setSelectedCell] = useState(null);

  useEffect(() => {
    fetchJson("/intelligence/friction-matrix?top=15", null)
      .then((d) => { setData(d); setLoading(false); })
      .catch(() => setLoading(false));
  }, []);

  const option = useMemo(() => buildFrictionHeatmapOption(data), [data]);

  const handleChartClick = useCallback((params) => {
    if (!data || !params.data) return;
    const [x, y] = params.data;
    const cell = data.matrix?.[y]?.[x];
    if (cell && cell.score > 0) setSelectedCell(cell);
  }, [data]);

  const chartEvents = useMemo(() => ({ click: handleChartClick }), [handleChartClick]);

  const chartHeight = chartMaxHeight
    ? Math.min(chartMaxHeight, Math.max(240, (data?.airlines?.length || 0) * 24 + 80))
    : Math.max(280, (data?.airlines?.length || 0) * 28 + 100);

  const skeleton = (
    <div className="fm-skeleton">
      {[...Array(5)].map((_, i) => (
        <div key={i} className="osm-shimmer" style={{ height: 18, marginBottom: 4 }} />
      ))}
    </div>
  );

  const body = loading ? (
    skeleton
  ) : !data || !data.airlines?.length ? (
    emptyContent || <p className="muted-copy">{t("semantic:friction.empty")}</p>
  ) : (
    <>
      <div className={`fm-chart-wrap ${bare ? "fm-chart-wrap--bounded" : ""}`.trim()}>
        <Suspense fallback={<div className="chart-skeleton tactical" style={{ height: chartHeight }} />}>
          <ReactECharts
            option={option}
            style={{ height: chartHeight, width: "100%" }}
            notMerge
            lazyUpdate
            onEvents={chartEvents}
            opts={{ renderer: "canvas" }}
          />
        </Suspense>
      </div>
      {data.metrics?.riskiest_airlines?.length > 0 && (
        <div className="fm-risk-strip">
          {data.metrics.riskiest_airlines.map((a) => (
            <span className="fm-risk-chip" key={a.slug}>
              <span className={`fm-risk-dot fm-risk-dot--${severityLabel(a.friction_score)}`} />
              {a.slug} <em>{a.friction_score}</em>
            </span>
          ))}
        </div>
      )}
    </>
  );

  if (bare) {
    return (
      <div className={`benchmark-friction-inner ${className}`.trim()}>
        {body}
        {selectedCell && (
          <DrilldownPanel cell={selectedCell} onClose={() => setSelectedCell(null)} />
        )}
      </div>
    );
  }

  if (loading) {
    return (
      <PanelShell title={t("semantic:friction.title")} accent="warning">
        {skeleton}
      </PanelShell>
    );
  }

  if (!data || !data.airlines?.length) {
    return (
      <PanelShell title={t("semantic:friction.title")} accent="warning">
        <p className="muted-copy">{t("semantic:friction.empty")}</p>
      </PanelShell>
    );
  }

  return (
    <>
      <PanelShell
        title={t("semantic:friction.title")}
        subtitle={t("semantic:friction.subtitle")}
        accent="warning"
        badges={<MetricsBadges metrics={data.metrics} />}
      >
        {body}
      </PanelShell>
      {selectedCell && (
        <DrilldownPanel cell={selectedCell} onClose={() => setSelectedCell(null)} />
      )}
    </>
  );
}

export const FrictionMatrix = memo(FrictionMatrixInner);
