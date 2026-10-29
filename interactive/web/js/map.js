// The map: dark basemap and globe intro, the data layers, and every transition between states.
import { circleRing, toLngLat, unionEdge } from "./geometry.js";

const STYLE_URL = "https://tiles.openfreemap.org/styles/positron";
const GLYPHS = "https://tiles.openfreemap.org/fonts/{fontstack}/{range}.pbf";
const IMAGERY = "https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/BlueMarble_ShadedRelief_Bathymetry/default/GoogleMapsCompatible_Level8/{z}/{y}/{x}.jpeg";
const RELIEF = "https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png";

export const COLORS = {
  land: "#16181c",
  plane: "#101215",
  raw: "rgba(235, 235, 240, 0.9)",
  core: "#ff7a40",
  noise: "rgba(166, 166, 172, 0.85)",
  outline: "rgba(6, 7, 9, 0.75)",
  accent: "#0a84ff",
  accentLine: "rgba(64, 156, 255, 0.9)",
  reach: "#342720",
  reachTarget: "#5e3723",
  edge: "rgba(255, 122, 64, 0.5)",
  edgeTarget: "rgba(255, 158, 112, 0.95)",
  refRing: "#ff9a62",
  clusterName: "#ffb48e",
};

// Role codes shared with the server: -2 hidden, -1 not yet clustered, 0 core, 1 border, 2 noise.
// Every visible dot keeps a thin dark outline so overlapping quakes stay separate.
const ROLE_COLOR = (role) => ["match", role, -2, "rgba(235, 235, 240, 0)", 0, COLORS.core, 1, COLORS.land, 2, COLORS.noise, COLORS.raw];
const ROLE_STROKE = (role) => ["match", role, -2, "rgba(0, 0, 0, 0)", 1, COLORS.core, COLORS.outline];
const ROLE_STROKE_WIDTH = (role) => ["match", role, -2, 0, 1, 1.6, 0.8];
const ROLE_SIZE = (role) => ["match", role, -2, 0, 2, 0.88, 1];
// The soft light under cluster members; noise and unclustered points get none.
const ROLE_GLOW = (role) => ["match", role, 0, 0.24, 1, 0.12, 0];

// OpenFreeMap Positron, recoloured after Apple Maps' dark appearance.
const PAINT = {
  background: { "background-color": COLORS.land },
  park: { "fill-color": "#18201b" },
  water: { "fill-color": "#0a1017" },
  landcover_ice_shelf: { "fill-color": "#1d2024" },
  landcover_glacier: { "fill-color": "#1d2024" },
  landuse_residential: { "fill-color": "#191b20" },
  landcover_wood: { "fill-color": "#171f1a" },
  waterway: { "line-color": "#0a1017" },
  building: { "fill-color": "#1e2126" },
  tunnel_motorway_casing: { "line-color": "#1b1d21" },
  tunnel_motorway_inner: { "line-color": "#272a2f" },
  road_area_pier: { "fill-color": COLORS.land },
  road_pier: { "line-color": COLORS.land },
  highway_path: { "line-color": "#202328" },
  highway_minor: { "line-color": "#25282d" },
  highway_major_casing: { "line-color": "#191b1f" },
  highway_major_inner: { "line-color": "#2e3136" },
  highway_major_subtle: { "line-color": "#2a2d32" },
  highway_motorway_casing: { "line-color": "#191b1f" },
  highway_motorway_inner: { "line-color": "#3a3d43" },
  highway_motorway_subtle: { "line-color": "#2f3237" },
  highway_motorway_bridge_casing: { "line-color": "#191b1f" },
  highway_motorway_bridge_inner: { "line-color": "#3a3d43" },
  boundary_2: { "line-color": "#4a4d54" },
  boundary_3: { "line-color": "#34373d" },
  boundary_disputed: { "line-color": "#3d4047" },
};
const TEXT = {
  label_city: "#d1d1d6", label_city_capital: "#d1d1d6", label_town: "#a1a1a6", label_village: "#7c7c80",
  label_other: "#7c7c80", label_state: "#636366", label_country_1: "#8e8e93", label_country_2: "#8e8e93",
  label_country_3: "#8e8e93", water_name_point_label: "#4f6d8a", water_name_line_label: "#4f6d8a",
};
const HIDE = new Set([
  "highway-shield-non-us", "highway-shield-us-interstate", "road_shield_us", "highway-name-path",
  "highway-name-minor", "highway-name-major", "airport", "aeroway-taxiway", "aeroway-runway-casing",
  "aeroway-area", "aeroway-runway", "railway_transit", "railway_transit_dashline", "railway_service",
  "railway_service_dashline", "railway", "railway_dashline", "waterway_line_label",
]);
const FOCUS_LAYERS = {
  "focus-fill": ["fill-opacity"], "focus-ring": ["line-opacity"], "focus-link": ["line-opacity"],
  "focus-halo": ["circle-opacity"], "focus-dot": ["circle-opacity", "circle-stroke-opacity"], "focus-label": ["text-opacity"],
};
const ANSWER_LAYERS = {
  "answer-ring": ["line-opacity"], "answer-allowed": ["line-opacity"], "answer-route-casing": ["line-opacity"],
  "answer-route": ["line-opacity"], "answer-core": ["circle-opacity", "circle-stroke-opacity"],
  "answer-dest": ["circle-opacity", "circle-stroke-opacity"], "answer-label": ["text-opacity"],
};
const EMPTY = { type: "FeatureCollection", features: [] };
const kind = (value) => ["==", ["get", "kind"], value];
const ROUND = { "line-cap": "round", "line-join": "round" };

const reducedMotion = () => window.matchMedia("(prefers-reduced-motion: reduce)").matches;
const easeOut = (t) => 1 - (1 - t) ** 3;
const easeInOut = (t) => (t < 0.5 ? 4 * t * t * t : 1 - (-2 * t + 2) ** 3 / 2);
const lerp = (a, b, t) => [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t];

// Run `frame(progress)` once per animation frame for `duration` ms, with ease-out.
function tween(duration, frame) {
  if (duration <= 0 || reducedMotion()) {
    frame(1);
    return Promise.resolve();
  }
  return new Promise((resolve) => {
    const start = performance.now();
    const step = (now) => {
      const t = Math.min(1, (now - start) / duration);
      frame(easeOut(t));
      if (t < 1) requestAnimationFrame(step);
      else resolve();
    };
    requestAnimationFrame(step);
  });
}

function insertBefore(layers, id, layer) {
  const index = layers.findIndex((l) => l.id === id);
  layers.splice(index < 0 ? layers.length : index, 0, layer);
}

async function buildStyle() {
  let style;
  try {
    const response = await fetch(STYLE_URL, { signal: AbortSignal.timeout(8000) });
    if (!response.ok) throw new Error(`basemap style ${response.status}`);
    style = await response.json();
    for (const layer of style.layers) {
      layer.metadata = { ...layer.metadata, base: true };
      if (PAINT[layer.id]) layer.paint = { ...layer.paint, ...PAINT[layer.id] };
      if (layer.type === "symbol") {
        layer.minzoom = Math.max(layer.minzoom || 0, 4.4); // a clean globe; labels arrive with the map
        layer.paint = {
          ...layer.paint,
          "text-halo-color": "rgba(8, 9, 11, 0.85)", "text-halo-width": 1.2, "text-halo-blur": 0.4, "icon-opacity": 0,
          ...(TEXT[layer.id] ? { "text-color": TEXT[layer.id] } : {}),
        };
      }
      if (HIDE.has(layer.id)) layer.layout = { ...layer.layout, visibility: "none" };
    }
    style.sources.relief = {
      type: "raster-dem", tiles: [RELIEF], encoding: "terrarium", tileSize: 256, maxzoom: 12,
      attribution: "Relief: AWS Terrain Tiles",
    };
    style.sources.imagery = {
      type: "raster", tiles: [IMAGERY], tileSize: 256, maxzoom: 8, attribution: "Globe: NASA Blue Marble via GIBS",
    };
    insertBefore(style.layers, "water", {
      id: "relief", type: "hillshade", source: "relief", minzoom: 3.5, metadata: { base: true },
      paint: {
        "hillshade-exaggeration": 0.45,
        "hillshade-shadow-color": "rgba(0, 0, 0, 0.6)",
        "hillshade-highlight-color": "rgba(255, 255, 255, 0.06)",
        "hillshade-accent-color": "rgba(0, 0, 0, 0.3)",
      },
    });
    insertBefore(style.layers, style.layers.find((l) => l.type === "symbol")?.id, {
      id: "imagery", type: "raster", source: "imagery", maxzoom: 5, metadata: { base: true },
      paint: { "raster-opacity": ["interpolate", ["linear"], ["zoom"], 2.8, 1, 4.6, 0], "raster-fade-duration": 150 },
    });
  } catch (error) {
    console.warn("Basemap unavailable; continuing on a plain background.", error);
    style = {
      version: 8, glyphs: GLYPHS, sources: {},
      layers: [{ id: "background", type: "background", metadata: { base: true }, paint: { "background-color": COLORS.land } }],
    };
  }
  // Globe while zoomed out, flat Mercator from regional zoom on, so eps circles stay circles.
  style.projection = { type: ["interpolate", ["linear"], ["zoom"], 3.4, "vertical-perspective", 5.2, "mercator"] };
  style.sky = { "atmosphere-blend": ["interpolate", ["linear"], ["zoom"], 0, 1, 3.2, 1, 4.6, 0] };
  style.light = { anchor: "map", position: [1.5, 90, 80] };
  style.transition = { duration: 300, delay: 0 };
  return style;
}

// Feature-state inputs shared by the point and glow layers.
const STATE = {
  t: ["coalesce", ["feature-state", "t"], 1],
  from: ["coalesce", ["feature-state", "from"], -2],
  to: ["coalesce", ["feature-state", "to"], -2],
  dim: ["coalesce", ["feature-state", "dim"], 0],
};
const blend = (of) => ["interpolate", ["linear"], STATE.t, 0, of(STATE.from), 1, of(STATE.to)];

function pointPaint() {
  const neighbor = ["boolean", ["feature-state", "neighbor"], false];
  // Points that change role swell briefly (sin peaks halfway through the change).
  const pulse = ["+", 1, ["*", 0.5, ["sin", ["*", ["pi"], STATE.t]]]];
  // Every quake gets at least a readable dot; magnitude adds to it.
  const base = ["+", 2.6, ["*", ["max", 0, ["-", ["get", "mag"], 2]], 1.25]];
  const radius = (scale) => ["*", base, scale, blend(ROLE_SIZE), pulse];
  const opacity = ["-", 1, ["*", 0.8, STATE.dim]];
  return {
    "circle-radius": ["interpolate", ["linear"], ["zoom"], 4, radius(0.8), 6, radius(1), 8, radius(1.3), 11, radius(2)],
    "circle-color": blend(ROLE_COLOR),
    "circle-stroke-color": ["case", neighbor, COLORS.accent, blend(ROLE_STROKE)],
    "circle-stroke-width": ["case", neighbor, 1.6, blend(ROLE_STROKE_WIDTH)],
    "circle-opacity": opacity,
    "circle-stroke-opacity": opacity,
  };
}

// A soft warm light under cluster members. Overlapping glows add up, so dense clusters read as
// brighter patches from far away; it fades as you zoom in so it never hides an eps circle.
function glowPaint() {
  const strength = ["*", blend(ROLE_GLOW), ["-", 1, STATE.dim]];
  return {
    "circle-radius": ["interpolate", ["linear"], ["zoom"], 4, 7, 6, 10, 9, 18, 12, 30],
    "circle-color": COLORS.core,
    "circle-blur": 1,
    "circle-opacity": ["interpolate", ["linear"], ["zoom"], 6.5, strength, 9.5, 0],
  };
}

// A label at the middle of a segment: above it when the segment runs sideways, to its right when it runs up or down.
function midLabel(affine, a, b, text) {
  const sideways = Math.abs(b[0] - a[0]) >= Math.abs(b[1] - a[1]);
  return {
    type: "Feature",
    properties: { kind: "label", text, anchor: sideways ? "bottom" : "left", offset: sideways ? [0, -0.6] : [0.9, 0] },
    geometry: { type: "Point", coordinates: toLngLat(affine, [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2]) },
  };
}

export class ExplorerMap {
  static async create(container, sheet, handlers) {
    const style = await buildStyle();
    return new ExplorerMap(container, sheet, handlers, style);
  }

  constructor(container, sheet, handlers, style) {
    this.sheet = sheet;
    this.handlers = handlers;
    this.dataset = null;
    this.points = null;
    this.roles = [];         // the role each point is moving to
    this.motion = new Map(); // point index -> running role change
    this.waits = [];         // promises waiting for a set of role changes to finish
    this.progress = null;
    this.dim = [];
    this.neighbors = [];
    this.reach = "a";        // which of the two reach layers is showing
    this.tokens = { focus: 0, answer: 0, dim: 0 };
    this.spinning = false;
    this.map = new maplibregl.Map({
      container, style, center: [-64, 24], zoom: 1.6, minZoom: 1, maxZoom: 14,
      attributionControl: false, dragRotate: false, pitchWithRotate: false, touchPitch: false, maxPitch: 0,
      renderWorldCopies: false,
    });
    this.map.touchZoomRotate.disableRotation();
    this.map.keyboard.disableRotation();
    this.map.addControl(new maplibregl.AttributionControl({ compact: true }), "bottom-right");
    this.scale = new maplibregl.ScaleControl({ maxWidth: 90, unit: "metric" });
    this.ready = new Promise((resolve) => this.map.once("load", () => { this.addLayers(); this.bindEvents(); resolve(); }));
  }

  addLayers() {
    const map = this.map;
    for (const id of ["points", "names", "reach-a", "reach-b", "focus", "answer"]) map.addSource(id, { type: "geojson", data: EMPTY });
    const underRoads = map.getLayer("tunnel_motorway_casing") ? "tunnel_motorway_casing" : undefined;
    const underLabels = map.getStyle().layers.find((l) => l.type === "symbol" && l.metadata?.base)?.id;
    // Two copies of each cluster's reach let a parameter change cross-fade instead of jump.
    // The fill sits under the roads like any map area; the thin edge sits above them.
    const fade = { duration: 520 };
    const edgeWidth = (extra) => ["interpolate", ["linear"], ["zoom"], 5, 0.7 + extra, 9, 1.2 + extra, 12, 1.6 + extra];
    for (const copy of ["a", "b"]) {
      const source = `reach-${copy}`;
      map.addLayer({ id: `reach-${copy}`, type: "fill", source, filter: kind("disc"),
        paint: { "fill-color": COLORS.reach, "fill-opacity": 0, "fill-opacity-transition": fade } }, underRoads);
      map.addLayer({ id: `target-${copy}`, type: "fill", source, filter: ["all", kind("disc"), ["==", ["get", "cluster"], -1]],
        paint: { "fill-color": COLORS.reachTarget, "fill-opacity": 0, "fill-opacity-transition": fade } }, underRoads);
      map.addLayer({ id: `edge-${copy}`, type: "line", source, filter: kind("edge"), layout: ROUND,
        paint: { "line-color": COLORS.edge, "line-width": edgeWidth(0), "line-opacity": 0, "line-opacity-transition": fade } }, underLabels);
      map.addLayer({ id: `target-edge-${copy}`, type: "line", source, filter: ["all", kind("edge"), ["==", ["get", "cluster"], -1]], layout: ROUND,
        paint: { "line-color": COLORS.edgeTarget, "line-width": edgeWidth(0.5), "line-opacity": 0, "line-opacity-transition": fade } }, underLabels);
    }
    map.addLayer({ id: "focus-fill", type: "fill", source: "focus", filter: kind("circle"),
      paint: { "fill-color": "rgba(10, 132, 255, 0.13)" } });
    map.addLayer({ id: "answer-ring", type: "line", source: "answer", filter: kind("ref-circle"),
      paint: { "line-color": COLORS.refRing, "line-width": 1.4, "line-dasharray": [2, 1.5] } });
    map.addLayer({ id: "glow", type: "circle", source: "points", paint: glowPaint() }, underLabels);
    map.addLayer({ id: "points", type: "circle", source: "points", layout: { "circle-sort-key": ["get", "mag"] }, paint: pointPaint() });
    // Cluster names sit just above each cluster like place names; larger clusters win when labels collide.
    map.addLayer({ id: "cluster-names", type: "symbol", source: "names",
      layout: {
        "text-field": ["get", "name"], "text-font": ["Noto Sans Regular"],
        "text-size": ["interpolate", ["linear"], ["zoom"], 5, 11.5, 10, 13.5],
        "text-anchor": "bottom", "text-offset": [0, -0.6], "text-letter-spacing": 0.02, "text-padding": 4,
        "symbol-sort-key": ["-", 0, ["get", "size"]],
      },
      paint: {
        "text-color": COLORS.clusterName, "text-halo-color": "rgba(8, 9, 11, 0.9)", "text-halo-width": 1.6,
        "text-opacity": 0, "text-opacity-transition": { duration: 600 },
      } });
    map.addLayer({ id: "focus-ring", type: "line", source: "focus", filter: kind("circle"),
      paint: { "line-color": COLORS.accentLine, "line-width": 1.3 } });
    map.addLayer({ id: "answer-allowed", type: "line", source: "answer", filter: kind("allowed"),
      paint: { "line-color": "rgba(64, 156, 255, 0.6)", "line-width": 1.5, "line-dasharray": [2, 2] } });
    map.addLayer({ id: "focus-link", type: "line", source: "focus", filter: kind("link"), layout: ROUND,
      paint: { "line-color": "#8e8e93", "line-width": 1.8, "line-dasharray": [0, 2.2] } });
    map.addLayer({ id: "answer-route-casing", type: "line", source: "answer", filter: kind("route"), layout: ROUND,
      paint: { "line-color": "#08090b", "line-width": 8 } });
    map.addLayer({ id: "answer-route", type: "line", source: "answer", filter: kind("route"), layout: ROUND,
      paint: { "line-color": COLORS.accent, "line-width": 4.5 } });
    map.addLayer({ id: "answer-core", type: "circle", source: "answer", filter: kind("ref-core"),
      paint: { "circle-radius": 6, "circle-color": COLORS.core, "circle-stroke-color": "#08090b", "circle-stroke-width": 2 } });
    map.addLayer({ id: "answer-dest", type: "circle", source: "answer", filter: kind("dest"),
      paint: { "circle-radius": 6.5, "circle-color": "#08090b", "circle-stroke-color": COLORS.accent, "circle-stroke-width": 3 } });
    map.addLayer({ id: "focus-halo", type: "circle", source: "focus", filter: kind("dot"),
      paint: { "circle-radius": 15, "circle-color": "rgba(10, 132, 255, 0.22)" } });
    map.addLayer({ id: "focus-dot", type: "circle", source: "focus", filter: kind("dot"),
      paint: { "circle-radius": 6.5, "circle-color": COLORS.accent, "circle-stroke-color": "#ffffff", "circle-stroke-width": 2.5 } });
    // Distance labels sit beside their line's midpoint; see midLabel().
    const label = (font, color) => ({
      layout: {
        "text-field": ["get", "text"], "text-font": [font], "text-size": 12.5,
        "text-anchor": ["get", "anchor"], "text-offset": ["get", "offset"],
        "text-allow-overlap": true, "text-ignore-placement": true,
      },
      paint: { "text-color": color, "text-halo-color": "rgba(8, 9, 11, 0.9)", "text-halo-width": 2 },
    });
    map.addLayer({ id: "focus-label", type: "symbol", source: "focus", filter: kind("label"), ...label("Noto Sans Regular", "#e5e5ea") });
    map.addLayer({ id: "answer-label", type: "symbol", source: "answer", filter: kind("label"), ...label("Noto Sans Bold", "#64b0ff") });
  }

  bindEvents() {
    const map = this.map;
    map.on("mousemove", "points", (event) => {
      map.getCanvas().style.cursor = "pointer";
      this.handlers.hover(event.features[0].id, event.originalEvent);
    });
    map.on("mouseleave", "points", () => {
      map.getCanvas().style.cursor = "";
      this.handlers.hover(null);
    });
    map.on("click", (event) => {
      const { x, y } = event.point;
      const hit = map.queryRenderedFeatures([[x - 6, y - 6], [x + 6, y + 6]], { layers: ["points"] })[0];
      this.handlers.click(hit ? hit.id : null, event.lngLat);
    });
    for (const type of ["mousedown", "touchstart", "wheel"]) map.on(type, () => { this.spinning = false; });
  }

  padding() {
    const box = this.sheet.getBoundingClientRect();
    if (window.innerWidth <= 760) return { top: 56, right: 24, bottom: window.innerHeight - box.top + 24, left: 24 };
    return { top: 56, right: 72, bottom: 56, left: box.right + 40 };
  }

  // Turn the globe west to east, the way the Earth turns, bringing North America round.
  spin() {
    this.spinning = true;
    const step = () => {
      if (!this.spinning) return;
      const center = this.map.getCenter();
      this.map.jumpTo({ center: [center.lng - 0.045, center.lat] });
      requestAnimationFrame(step);
    };
    requestAnimationFrame(step);
  }

  // Pull back out to the globe over the current spot.
  flyGlobe() {
    this.spinning = false;
    const { lng, lat } = this.map.getCenter();
    return new Promise((resolve) => {
      this.map.once("moveend", resolve);
      this.map.flyTo({ center: [lng, Math.max(-50, Math.min(50, lat))], zoom: 1.6, duration: 3200, curve: 1.42, easing: easeInOut, essential: true });
    });
  }

  flyTo(bounds, duration = 5200) {
    this.spinning = false;
    const camera = this.map.cameraForBounds(bounds, { padding: this.padding() });
    return new Promise((resolve) => {
      this.map.once("moveend", resolve);
      this.map.flyTo({ center: camera.center, zoom: camera.zoom, duration, curve: 1.42, easing: easeInOut, essential: true });
    });
  }

  fit(bounds, options = {}) {
    this.map.fitBounds(bounds, { padding: this.padding(), duration: 900, ...options });
  }

  zoom(delta) {
    this.map.easeTo({ zoom: this.map.getZoom() + delta, duration: 250 });
  }

  // Zoom to the given data points plus a margin, so eps circles are big enough to read.
  frame(xys, margin) {
    const xs = xys.map((p) => p[0]);
    const ys = xys.map((p) => p[1]);
    const sw = toLngLat(this.dataset.affine, [Math.min(...xs) - margin, Math.min(...ys) - margin]);
    const ne = toLngLat(this.dataset.affine, [Math.max(...xs) + margin, Math.max(...ys) + margin]);
    this.map.fitBounds([sw, ne], { padding: this.padding(), maxZoom: 13, duration: 1100, essential: true });
  }

  showScale(on) {
    if (on && !this.map.hasControl(this.scale)) this.map.addControl(this.scale, "bottom-right");
    if (!on && this.map.hasControl(this.scale)) this.map.removeControl(this.scale);
  }

  setDataset(dataset, points) {
    this.dataset = dataset;
    this.points = points;
    const map = this.map;
    this.motion.clear();
    for (const wait of this.waits) wait.resolve();
    this.waits = [];
    this.progress = null;
    map.removeFeatureState({ source: "points" });
    this.roles = points.xy.map(() => -2);
    this.dim = points.xy.map(() => 0);
    this.neighbors = [];
    const mag = dataset.kind === "geo" ? null : 3;
    map.getSource("points").setData({
      type: "FeatureCollection",
      features: points.xy.map((xy, i) => ({
        type: "Feature", id: i,
        geometry: { type: "Point", coordinates: toLngLat(dataset.affine, xy) },
        properties: { mag: mag ?? points.meta[i].mag },
      })),
    });
    const geo = dataset.kind === "geo";
    for (const layer of map.getStyle().layers) {
      if (!layer.metadata?.base || layer.id === "background") continue;
      map.setLayoutProperty(layer.id, "visibility", geo && !HIDE.has(layer.id) ? "visible" : "none");
    }
    map.setPaintProperty("background", "background-color", geo ? COLORS.land : COLORS.plane);
    this.setReach(null);
    this.setClusterNames(null);
    this.clearFocus(false);
  }

  // One label per cluster, centred above its highest member.
  setClusterNames(clustering) {
    const features = [];
    if (clustering) {
      const spans = new Map();
      clustering.labels.forEach((label, i) => {
        if (label < 0) return;
        const [x, y] = this.points.xy[i];
        const span = spans.get(label) ?? { x: 0, n: 0, top: -Infinity };
        span.x += x;
        span.n += 1;
        span.top = Math.max(span.top, y);
        spans.set(label, span);
      });
      for (const cluster of clustering.clusters) {
        const span = spans.get(cluster.id);
        if (!span) continue;
        features.push({
          type: "Feature", properties: { name: cluster.name, size: cluster.size },
          geometry: { type: "Point", coordinates: toLngLat(this.dataset.affine, [span.x / span.n, span.top]) },
        });
      }
    }
    this.map.getSource("names").setData({ type: "FeatureCollection", features });
    this.map.setPaintProperty("cluster-names", "text-opacity", clustering ? 1 : 0);
  }

  // Move every point to a new role. With `order`, points start one after another across `total` ms.
  setRoles(roles, { order = null, total = 0, duration = 420, onProgress = null } = {}) {
    const now = performance.now();
    const rank = new Map((order || []).map((i, k) => [i, k]));
    const stagger = order?.length ? Math.max(0, total - duration) / order.length : 0;
    const instant = reducedMotion();
    const changed = new Set();
    roles.forEach((next, i) => {
      if (next === this.roles[i]) return;
      const running = this.motion.get(i);
      const from = running && running.progress < 0.5 ? running.from : this.roles[i];
      this.roles[i] = next;
      if (instant) {
        this.motion.delete(i);
        this.map.setFeatureState({ source: "points", id: i }, { from: next, to: next, t: 1 });
        return;
      }
      this.motion.set(i, { from, start: now + (rank.get(i) ?? 0) * stagger, duration, progress: 0 });
      this.map.setFeatureState({ source: "points", id: i }, { from, to: next, t: 0 });
      changed.add(i);
    });
    if (onProgress) {
      if (instant || !order?.length) onProgress(order?.length ?? 0);
      else this.progress = { onProgress, start: now, stagger, count: order.length };
    }
    const finished = new Promise((resolve) => (changed.size ? this.waits.push({ ids: changed, resolve }) : resolve()));
    this.animateRoles();
    return finished;
  }

  animateRoles() {
    if (this.animating) return;
    this.animating = true;
    const step = (now) => {
      for (const [i, m] of this.motion) {
        if (now < m.start) continue;
        m.progress = Math.min(1, (now - m.start) / m.duration);
        this.map.setFeatureState({ source: "points", id: i }, { t: easeOut(m.progress) });
        if (m.progress >= 1) {
          this.motion.delete(i);
          for (const wait of this.waits) wait.ids.delete(i);
        }
      }
      if (this.progress) {
        const { onProgress, start, stagger, count } = this.progress;
        const started = stagger ? Math.min(count, Math.floor((now - start) / stagger) + 1) : count;
        onProgress(started);
        if (started >= count) this.progress = null;
      }
      this.waits = this.waits.filter((wait) => (wait.ids.size ? true : (wait.resolve(), false)));
      if (this.motion.size || this.progress) requestAnimationFrame(step);
      else this.animating = false;
    };
    requestAnimationFrame(step);
  }

  // Each cluster's reach: the union of eps discs around its core points, plus that union's outer edge.
  // Updates draw into the hidden copy and cross-fade.
  setReach(clustering, eps) {
    const next = this.reach === "a" ? "b" : "a";
    const affine = this.dataset.affine;
    const features = [];
    for (const cluster of clustering?.clusters ?? []) {
      const centers = cluster.core.map((i) => this.points.xy[i]);
      for (const center of centers) {
        features.push({
          type: "Feature", properties: { kind: "disc", cluster: cluster.id },
          geometry: { type: "Polygon", coordinates: [circleRing(affine, center, eps, 48)] },
        });
      }
      features.push({
        type: "Feature", properties: { kind: "edge", cluster: cluster.id },
        geometry: { type: "MultiLineString", coordinates: unionEdge(affine, centers, eps, 48) },
      });
    }
    this.map.getSource(`reach-${next}`).setData({ type: "FeatureCollection", features });
    const show = (copy, on) => {
      for (const layer of [`reach-${copy}`, `target-${copy}`]) this.map.setPaintProperty(layer, "fill-opacity", on ? 1 : 0);
      for (const layer of [`edge-${copy}`, `target-edge-${copy}`]) this.map.setPaintProperty(layer, "line-opacity", on ? 1 : 0);
    };
    show(next, Boolean(clustering));
    show(this.reach, false);
    this.reach = next;
  }

  setTarget(cluster) {
    const id = cluster ?? -1;
    for (const copy of ["a", "b"]) {
      this.map.setFilter(`target-${copy}`, ["all", kind("disc"), ["==", ["get", "cluster"], id]]);
      this.map.setFilter(`target-edge-${copy}`, ["all", kind("edge"), ["==", ["get", "cluster"], id]]);
    }
  }

  // Fade every point outside cluster `keep` (or bring them all back when keep is null).
  setDim(labels, keep) {
    const goal = labels.map((label) => (keep !== null && label !== keep ? 1 : 0));
    const start = this.dim.slice();
    const changed = goal.flatMap((v, i) => (Math.abs(v - start[i]) > 1e-3 ? [i] : []));
    if (!changed.length) return;
    const token = ++this.tokens.dim;
    tween(340, (t) => {
      if (token !== this.tokens.dim) return;
      for (const i of changed) {
        this.dim[i] = start[i] + (goal[i] - start[i]) * t;
        this.map.setFeatureState({ source: "points", id: i }, { dim: this.dim[i] });
      }
    });
  }

  setNeighbors(neighbors) {
    for (const i of this.neighbors) this.map.setFeatureState({ source: "points", id: i }, { neighbor: false });
    this.neighbors = neighbors;
    for (const i of neighbors) this.map.setFeatureState({ source: "points", id: i }, { neighbor: true });
  }

  fade(layers, on) {
    for (const [layer, properties] of Object.entries(layers)) {
      for (const property of properties) this.map.setPaintProperty(layer, property, on ? 1 : 0);
    }
  }

  // A one-time callout on a single point: a ring and ripples around it and a pill above. It follows
  // the map. Clicks on the point pass straight through; the pill does the same as clicking the point.
  // The marker element stays bare because MapLibre positions it and sets its opacity.
  showCoach(xy, text, onClick) {
    this.hideCoach(false);
    const element = document.createElement("div");
    element.innerHTML = '<div class="coachmark"><span class="ripple"></span><span class="ripple late"></span>'
      + '<span class="target"></span><button type="button" class="bubble"></button></div>';
    const bubble = element.querySelector(".bubble");
    bubble.textContent = text;
    bubble.addEventListener("click", (event) => {
      event.stopPropagation();
      onClick();
    });
    this.coach = new maplibregl.Marker({ element, anchor: "center" }).setLngLat(toLngLat(this.dataset.affine, xy)).addTo(this.map);
  }

  coachText(text) {
    if (this.coach) this.coach.getElement().querySelector(".bubble").textContent = text;
  }

  hideCoach(animate = true) {
    const marker = this.coach;
    if (!marker) return;
    this.coach = null;
    if (!animate) {
      marker.remove();
      return;
    }
    marker.getElement().firstChild.classList.add("leaving");
    setTimeout(() => marker.remove(), 260);
  }

  // Whether a data point is on screen and clear of the sheet and the map edges.
  inView(xy, margins = { top: 60, side: 24 }) {
    const p = this.map.project(toLngLat(this.dataset.affine, xy));
    const pad = this.padding();
    const { width, height } = this.map.getCanvas().getBoundingClientRect();
    return p.x > pad.left + margins.side - 40 && p.x < width - pad.right + 40 - margins.side
      && p.y > Math.max(pad.top, margins.top) && p.y < height - pad.bottom + 32;
  }

  // Hide or show the selection and its answer without forgetting them (the Data tab hides them).
  showOverlays(on) {
    this.fade(FOCUS_LAYERS, on);
    this.fade(ANSWER_LAYERS, on);
    for (const i of this.neighbors) this.map.setFeatureState({ source: "points", id: i }, { neighbor: on });
    if (on && this.routeShown) this.map.setPaintProperty("focus-label", "text-opacity", 0);
  }

  // The selected point, its eps circle and the link to the core point that explains it.
  // A new selection grows the circle from nothing; a parameter change resizes it from `fromEps`.
  showFocus({ point, eps, neighbors, link, fromEps = null }) {
    const affine = this.dataset.affine;
    const token = ++this.tokens.focus;
    const fresh = fromEps === null;
    if (fresh) this.clearAnswer(false);
    this.fade(FOCUS_LAYERS, true);
    this.setNeighbors(neighbors);
    const r0 = fresh ? 0 : fromEps;
    return tween(fresh ? 480 : 320, (t) => {
      if (token !== this.tokens.focus) return;
      const features = [
        { type: "Feature", properties: { kind: "circle" }, geometry: { type: "Polygon", coordinates: [circleRing(affine, point, r0 + (eps - r0) * t)] } },
        { type: "Feature", properties: { kind: "dot" }, geometry: { type: "Point", coordinates: toLngLat(affine, point) } },
      ];
      const reach = fresh ? Math.max(0, (t - 0.35) / 0.65) : 1;
      if (link && reach > 0) {
        features.push({ type: "Feature", properties: { kind: "link" },
          geometry: { type: "LineString", coordinates: [toLngLat(affine, point), toLngLat(affine, lerp(point, link.to, reach))] } });
        if (reach >= 1) features.push(midLabel(affine, point, link.to, link.text));
      }
      this.map.getSource("focus").setData({ type: "FeatureCollection", features });
    });
  }

  // The smallest move as a route. A new answer draws out from the point; an updated one slides from `previous`.
  // `allowed` ({ fixed, value }) draws the only line a constrained point may move along:
  // across the map when north (y) is fixed, down it when east (x) is fixed.
  showAnswer({ original, counterfactual, reference, eps, label, allowed = null, bounds, previous = null }) {
    const affine = this.dataset.affine;
    const token = ++this.tokens.answer;
    this.fade(ANSWER_LAYERS, true);
    // The route carries its own distance; the nearest-core distance would crowd it.
    this.routeShown = Boolean(counterfactual);
    this.map.setPaintProperty("focus-label", "text-opacity", counterfactual ? 0 : 1);
    if (!counterfactual) {
      const features = [];
      if (allowed) {
        const [[west, south], [east, north]] = bounds;
        const [lng, lat] = toLngLat(affine, allowed.fixed === 1 ? [0, allowed.value] : [allowed.value, 0]);
        const coordinates = allowed.fixed === 1 ? [[west, lat], [east, lat]] : [[lng, south], [lng, north]];
        features.push({ type: "Feature", properties: { kind: "allowed" }, geometry: { type: "LineString", coordinates } });
      }
      this.map.getSource("answer").setData({ type: "FeatureCollection", features });
      return Promise.resolve();
    }
    const from = previous ?? original;
    return tween(previous ? 360 : 620, (t) => {
      if (token !== this.tokens.answer) return;
      const end = lerp(from, counterfactual, t);
      const features = [
        { type: "Feature", properties: { kind: "ref-circle" }, geometry: { type: "Polygon", coordinates: [circleRing(affine, reference, eps)] } },
        { type: "Feature", properties: { kind: "route" }, geometry: { type: "LineString", coordinates: [toLngLat(affine, original), toLngLat(affine, end)] } },
        { type: "Feature", properties: { kind: "ref-core" }, geometry: { type: "Point", coordinates: toLngLat(affine, reference) } },
      ];
      if (previous || t > 0.8) features.push({ type: "Feature", properties: { kind: "dest" }, geometry: { type: "Point", coordinates: toLngLat(affine, end) } });
      if (t >= 1) features.push(midLabel(affine, original, counterfactual, label));
      this.map.getSource("answer").setData({ type: "FeatureCollection", features });
    });
  }

  // Fade the answer out, then empty it. `animate = false` empties it at once.
  clearAnswer(animate = true) {
    const token = ++this.tokens.answer;
    this.routeShown = false;
    this.map.setPaintProperty("focus-label", "text-opacity", 1);
    if (!animate) {
      this.map.getSource("answer").setData(EMPTY);
      return;
    }
    this.fade(ANSWER_LAYERS, false);
    setTimeout(() => {
      if (token === this.tokens.answer) this.map.getSource("answer").setData(EMPTY);
    }, 320);
  }

  clearFocus(animate = true) {
    const token = ++this.tokens.focus;
    this.setNeighbors([]);
    this.setTarget(null);
    this.clearAnswer(animate);
    if (!animate) {
      this.map.getSource("focus").setData(EMPTY);
      return;
    }
    this.fade(FOCUS_LAYERS, false);
    setTimeout(() => {
      if (token === this.tokens.focus) this.map.getSource("focus").setData(EMPTY);
    }, 320);
  }
}
