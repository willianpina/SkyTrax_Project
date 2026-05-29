/** Aviation operational basemap — light/dark harmonized with SkyTrax UI */

export const BASEMAP = {
  light: "https://basemaps.cartocdn.com/gl/positron-gl-style/style.json",
  dark: "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json",
};

export const PALETTE = {
  light: {
    ocean: "#243447",
    land: "#111827",
    border: "rgba(148, 163, 184, 0.22)",
    label: "#CBD5E1",
    arc: [37, 99, 235],
    arcRisk: [220, 38, 38],
    hub: [5, 150, 105],
    heat: [
      [255, 255, 255, 0],
      [36, 52, 71, 80],
      [37, 99, 235, 140],
      [245, 158, 11, 170],
      [220, 38, 38, 200],
    ],
  },
  dark: {
    ocean: "#243447",
    land: "#111827",
    border: "rgba(148, 163, 184, 0.22)",
    label: "#CBD5E1",
    arc: [96, 165, 250],
    arcRisk: [248, 113, 113],
    hub: [52, 211, 153],
    heat: [
      [17, 24, 39, 0],
      [36, 52, 71, 100],
      [96, 165, 250, 150],
      [251, 191, 36, 180],
      [248, 113, 113, 210],
    ],
  },
};

export function getBasemapStyle(theme = "light") {
  return theme === "dark" ? BASEMAP.dark : BASEMAP.light;
}

export function getPalette(theme = "light") {
  return theme === "dark" ? PALETTE.dark : PALETTE.light;
}

export function applyAviationBasemapTheme(map, theme = "light") {
  if (!map?.getStyle) return;
  const { ocean, land, border, label } = getPalette(theme);

  try {
    if (map.getLayer("background")) {
      map.setPaintProperty("background", "background-color", land);
    }
  } catch {
    /* optional layer */
  }

  for (const layer of map.getStyle()?.layers || []) {
    const id = layer.id || "";
    const type = layer.type;
    try {
      if (type === "fill" && /water|ocean|sea|lake/i.test(id)) {
        map.setPaintProperty(id, "fill-color", ocean);
        map.setPaintProperty(id, "fill-opacity", 0.92);
      }
      if (type === "fill" && /land|earth|country|continent|park/i.test(id)) {
        map.setPaintProperty(id, "fill-color", land);
      }
      if (type === "line" && /boundary|border|admin/i.test(id)) {
        map.setPaintProperty(id, "line-color", border);
        map.setPaintProperty(id, "line-opacity", 0.5);
      }
      if (type === "symbol" && /label|place|name/i.test(id)) {
        map.setPaintProperty(id, "text-color", label);
        map.setPaintProperty(id, "text-halo-color", land);
        map.setPaintProperty(id, "text-halo-width", 1);
      }
    } catch {
      /* ignore */
    }
  }
}
