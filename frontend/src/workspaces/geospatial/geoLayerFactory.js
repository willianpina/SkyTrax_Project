import { ArcLayer, GeoJsonLayer, ScatterplotLayer, TextLayer } from "@deck.gl/layers";
import { HeatmapLayer } from "@deck.gl/aggregation-layers";
import { TripsLayer } from "@deck.gl/geo-layers";
import { getPalette } from "./aviationMapTheme";

const EMPTY_FC = { type: "FeatureCollection", features: [] };

function hubColor(score, palette) {
  const rep = Number(score || 0.5);
  if (rep >= 0.75) return [...palette.hub, 220];
  return [100, 116, 139, 200];
}

function eventColor(priority, score) {
  const p = String(priority || "").toLowerCase();
  if (p === "critical") return [220, 38, 38, 210];
  if (p === "high") return [234, 88, 12, 200];
  if (p === "medium") return [245, 158, 11, 190];
  const s = Number(score || 0);
  return s >= 0.5 ? [245, 158, 11, 170] : [148, 163, 184, 150];
}

export function buildGeospatialLayers({
  airports,
  routes,
  events,
  zones,
  trips,
  toggles,
  tripTime,
  theme = "light",
}) {
  const palette = getPalette(theme);
  const layers = [];

  if (toggles.zones && zones?.features?.length) {
    layers.push(
      new GeoJsonLayer({
        id: "geo-zones",
        data: zones,
        pickable: false,
        stroked: true,
        filled: true,
        lineWidthMinPixels: 1,
        getFillColor: [36, 52, 71, 40],
        getLineColor: [148, 163, 184, 60],
        getLineWidth: 1,
        opacity: 0.75,
      }),
    );
  }

  if (toggles.heatmap && events.length) {
    layers.push(
      new HeatmapLayer({
        id: "geo-heat",
        data: events,
        getPosition: (d) => [Number(d.longitude), Number(d.latitude)],
        getWeight: (d) => Number(d.score || 0.2) + 0.1,
        radiusPixels: 36,
        intensity: 1.1,
        threshold: 0.04,
        colorRange: palette.heat,
      }),
    );
  }

  if (toggles.routes && routes.length) {
    layers.push(
      new ArcLayer({
        id: "geo-routes",
        data: routes,
        pickable: true,
        greatCircle: true,
        getSourcePosition: (d) => [Number(d.source_lng), Number(d.source_lat)],
        getTargetPosition: (d) => [Number(d.destination_lng), Number(d.destination_lat)],
        getSourceColor: (d) => {
          const risk = Number(d.risk_score || 0);
          return risk >= 0.55 ? [...palette.arcRisk, 170] : [...palette.arc, 150];
        },
        getTargetColor: [...palette.arc, 60],
        getWidth: (d) => Math.max(1, Math.min(4, Number(d.frequency || 1) / 120)),
        widthMinPixels: 1,
        widthMaxPixels: 4,
      }),
    );
  }

  if (toggles.trips && trips.length) {
    layers.push(
      new TripsLayer({
        id: "geo-trips",
        data: trips,
        pickable: false,
        trailLength: 120,
        currentTime: tripTime,
        fadeTrail: true,
        capRounded: true,
        jointRounded: true,
        getPath: (d) => d.path,
        getTimestamps: (d) => d.timestamps,
        getColor: (d) =>
          d.risk >= 0.55 ? [...palette.arcRisk, 160] : [...palette.arc, 150],
        getWidth: 2,
        widthMinPixels: 1.5,
        opacity: 0.75,
      }),
    );
  }

  if (toggles.hubs && airports.length) {
    layers.push(
      new ScatterplotLayer({
        id: "geo-hubs",
        data: airports,
        pickable: true,
        stroked: true,
        filled: true,
        radiusUnits: "pixels",
        radiusMinPixels: 3,
        radiusMaxPixels: 14,
        lineWidthMinPixels: 1,
        getPosition: (d) => [Number(d.longitude), Number(d.latitude)],
        getRadius: (d) => 3 + Number(d.hub_score || 0.35) * 9,
        getFillColor: (d) => hubColor(d.reputation_score, palette),
        getLineColor: [17, 24, 39, 180],
      }),
    );
  }

  if (toggles.alerts && events.length) {
    layers.push(
      new ScatterplotLayer({
        id: "geo-events",
        data: events.slice(0, 800),
        pickable: true,
        radiusUnits: "pixels",
        radiusMinPixels: 2,
        radiusMaxPixels: 8,
        getPosition: (d) => [Number(d.longitude), Number(d.latitude)],
        getRadius: (d) => 2 + Number(d.score || 0.1) * 5,
        getFillColor: (d) => eventColor(d.prioridade, d.score),
        stroked: false,
      }),
    );
  }

  if (toggles.labels && airports.length) {
    layers.push(
      new TextLayer({
        id: "geo-hub-labels",
        data: airports.filter((a) => Number(a.hub_score || 0) >= 0.68).slice(0, 36),
        pickable: false,
        getPosition: (d) => [Number(d.longitude), Number(d.latitude)],
        getText: (d) => d.iata || d.icao || "",
        getColor: theme === "light" ? [51, 65, 85, 230] : [203, 213, 225, 230],
        getSize: 10,
        fontFamily: "Inter, system-ui, sans-serif",
        fontWeight: 600,
        getPixelOffset: [0, 12],
        getTextAnchor: "middle",
      }),
    );
  }

  return layers;
}

export function emptyZones() {
  return EMPTY_FC;
}
