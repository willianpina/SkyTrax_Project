import React, { memo } from "react";
import { Pause, Play, RefreshCw } from "lucide-react";

const LAYER_KEYS = ["hubs", "routes", "heatmap", "alerts", "labels", "zones", "trips"];

function GeoHudInner({
  layerToggles,
  layerLabels,
  onToggleLayer,
  onReload,
  loading,
  timelinePlaying,
  onToggleTimeline,
  timelineProgress,
  onTimelineScrub,
  stats,
  seeded,
}) {
  return (
    <>
      <header className="geo-hud geo-hud--bar" role="toolbar" aria-label="Geospatial controls">
        <div className="geo-hud-pills">
          {LAYER_KEYS.map((key) => (
            <button
              key={key}
              type="button"
              className={`geo-hud-pill ${layerToggles[key] ? "geo-hud-pill--on" : ""}`}
              onClick={() => onToggleLayer(key)}
            >
              {layerLabels[key]}
            </button>
          ))}
        </div>
        <div className="geo-hud-metrics">
          {stats.map(({ key, label, value }) => (
            <span className="geo-hud-metric-inline" key={key}>
              <span className="geo-hud-metric-k">{label}</span>
              <span className="geo-hud-metric-v">{Number(value || 0).toLocaleString("en-US")}</span>
            </span>
          ))}
        </div>
        <div className="geo-hud-actions">
          {seeded ? <span className="geo-hud-tag">REF</span> : null}
          <span className="geo-hud-live">{loading ? "SYNC" : "LIVE"}</span>
          <button type="button" className="geo-hud-btn" onClick={onReload} disabled={loading} title="Sync">
            <RefreshCw size={12} className={loading ? "spin" : ""} />
          </button>
        </div>
      </header>

      <div className="geo-hud geo-hud--replay" aria-label="Flow replay">
        <button
          type="button"
          className="geo-hud-btn geo-hud-btn--icon"
          onClick={onToggleTimeline}
          aria-pressed={timelinePlaying}
          title={timelinePlaying ? "Pause" : "Play"}
        >
          {timelinePlaying ? <Pause size={11} /> : <Play size={11} />}
        </button>
        <input
          type="range"
          className="geo-hud-scrubber"
          min={0}
          max={1000}
          value={Math.round(timelineProgress * 1000)}
          onChange={(e) => onTimelineScrub(Number(e.target.value) / 1000)}
          aria-label="Replay"
        />
      </div>
    </>
  );
}

export const GeoHud = memo(GeoHudInner);
