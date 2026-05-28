import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import DeckGL from "@deck.gl/react";
import { Map as MapLibreMap } from "react-map-gl/maplibre";
import "maplibre-gl/dist/maplibre-gl.css";
import { useTheme } from "../../hooks/ThemeProvider";
import { useGeospatial } from "../../hooks/useGeospatial";
import { GeoHud } from "./GeoHud";
import { applyAviationBasemapTheme, getBasemapStyle } from "./aviationMapTheme";
import { buildGeospatialLayers } from "./geoLayerFactory";
import { buildTripsFromRoutes, tripAnimationBounds } from "./geoMath";
import "./geospatial.css";

const INITIAL_VIEW_STATE = {
  longitude: 10,
  latitude: 28,
  zoom: 1.75,
  pitch: 0,
  bearing: 0,
  minZoom: 0.8,
  maxZoom: 14,
};

const MAP_CONTROLLER = {
  inertia: 180,
  scrollZoom: { smooth: true },
  dragRotate: false,
  touchRotate: false,
  maxPitch: 0,
  minPitch: 0,
};

export default function GeospatialWorkspace() {
  const { t } = useTranslation(["command", "nav", "common"]);
  const { theme } = useTheme();
  const { airports, routes, events, zones, summary, loading, reload } = useGeospatial();
  const mapRef = useRef(null);

  const [viewState, setViewState] = useState(INITIAL_VIEW_STATE);
  const [layerToggles, setLayerToggles] = useState({
    hubs: true,
    routes: true,
    heatmap: true,
    alerts: true,
    labels: true,
    zones: true,
    trips: false,
  });
  const [timelinePlaying, setTimelinePlaying] = useState(false);
  const [timelineProgress, setTimelineProgress] = useState(0);

  const trips = useMemo(() => buildTripsFromRoutes(routes), [routes]);
  const { loopMs } = useMemo(() => tripAnimationBounds(trips), [trips]);
  const tripTime = timelineProgress * loopMs;

  useEffect(() => {
    if (!timelinePlaying || !layerToggles.trips || !trips.length) return undefined;
    let frame;
    let last = performance.now();
    const tick = (now) => {
      const delta = now - last;
      last = now;
      setTimelineProgress((p) => {
        const next = p + delta / loopMs;
        return next >= 1 ? next - 1 : next;
      });
      frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [timelinePlaying, layerToggles.trips, trips.length, loopMs]);

  const layers = useMemo(
    () =>
      buildGeospatialLayers({
        airports,
        routes,
        events,
        zones,
        trips,
        toggles: layerToggles,
        tripTime,
        theme,
      }),
    [airports, routes, events, zones, trips, layerToggles, tripTime, theme],
  );

  const layerLabels = useMemo(
    () => ({
      hubs: t("command:map.layers.coverage", { defaultValue: "Hubs" }),
      routes: t("command:map.layers.routes", { defaultValue: "Routes" }),
      heatmap: t("command:map.layers.risk", { defaultValue: "Heat" }),
      alerts: t("command:map.layers.alerts", { defaultValue: "Signals" }),
      labels: t("command:map.layers.labels", { defaultValue: "Labels" }),
      zones: t("nav:geo.zones", { defaultValue: "Zones" }),
      trips: t("nav:geo.trips", { defaultValue: "Flow" }),
    }),
    [t],
  );

  const stats = useMemo(
    () => [
      { key: "airports", label: t("nav:geo.airports", { defaultValue: "APT" }), value: summary.airport_count },
      { key: "routes", label: t("nav:geo.routes", { defaultValue: "RT" }), value: summary.route_count },
      { key: "events", label: t("nav:geo.events", { defaultValue: "EVT" }), value: summary.event_count },
      { key: "hubs", label: t("nav:geo.hubs", { defaultValue: "HUB" }), value: summary.hub_count },
    ],
    [summary, t],
  );

  const applyTheme = useCallback(
    (map) => {
      if (!map) return;
      applyAviationBasemapTheme(map, theme);
    },
    [theme],
  );

  const onMapLoad = useCallback(
    (event) => {
      const map = event.target;
      mapRef.current = map;
      applyTheme(map);
    },
    [applyTheme],
  );

  useEffect(() => {
    if (mapRef.current?.isStyleLoaded?.()) {
      applyTheme(mapRef.current);
    }
  }, [applyTheme, theme]);

  const onViewStateChange = useCallback(({ viewState: next }) => {
    setViewState({
      ...next,
      pitch: 0,
      bearing: 0,
    });
  }, []);

  const onToggleLayer = useCallback((key) => {
    setLayerToggles((prev) => ({ ...prev, [key]: !prev[key] }));
    if (key === "trips") setTimelinePlaying(false);
  }, []);

  const getTooltip = useCallback(({ object }) => {
    if (!object) return null;
    if (object.source_icao && object.destination_icao) {
      return {
        html: `<div class="geo-tooltip"><strong>${object.source_icao} → ${object.destination_icao}</strong><br/>Freq ${Math.round(Number(object.frequency || 0))} · Risk ${Number(object.risk_score || 0).toFixed(2)}</div>`,
      };
    }
    if (object.tipo_evento) {
      return {
        html: `<div class="geo-tooltip"><strong>${object.companhia || "Signal"}</strong><br/>${object.tipo_evento} · ${object.prioridade}</div>`,
      };
    }
    return {
      html: `<div class="geo-tooltip"><strong>${object.name || object.iata || "Airport"}</strong><br/>${object.city || ""} ${object.country || ""}</div>`,
    };
  }, []);

  return (
    <div className="geo-ops-canvas">
      <DeckGL
        className="geo-ops-deck"
        viewState={viewState}
        onViewStateChange={onViewStateChange}
        controller={MAP_CONTROLLER}
        layers={layers}
        getTooltip={getTooltip}
      >
        <MapLibreMap
          key={theme}
          mapStyle={getBasemapStyle(theme)}
          reuseMaps
          attributionControl={false}
          onLoad={onMapLoad}
        />
      </DeckGL>

      <GeoHud
        layerToggles={layerToggles}
        layerLabels={layerLabels}
        onToggleLayer={onToggleLayer}
        onReload={reload}
        loading={loading}
        timelinePlaying={timelinePlaying}
        onToggleTimeline={() => {
          setTimelinePlaying((p) => {
            const next = !p;
            if (next && !layerToggles.trips) {
              setLayerToggles((prev) => ({ ...prev, trips: true }));
            }
            return next;
          });
        }}
        timelineProgress={timelineProgress}
        onTimelineScrub={setTimelineProgress}
        stats={stats}
        seeded={summary.seeded}
      />

      {loading && airports.length === 0 ? (
        <div className="geo-ops-loading" role="status">
          {t("common:status.loading", { defaultValue: "Loading…" })}
        </div>
      ) : null}
    </div>
  );
}
