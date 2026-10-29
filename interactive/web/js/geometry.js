// Coordinates and wording shared by the map and the sheet.
// Data coordinates are what DBSCAN sees (metres for USGS, unitless for shapes);
// each dataset's affine map turns them into longitude and latitude for drawing.

export const toLngLat = (affine, [x, y]) => [affine.lon0 + x * affine.kx, affine.lat0 + y * affine.ky];

export const toData = (affine, { lng, lat }) => [(lng - affine.lon0) / affine.kx, (lat - affine.lat0) / affine.ky];

// A circle of `radius` data units, as a closed longitude/latitude ring.
export function circleRing(affine, [cx, cy], radius, steps = 72) {
  const ring = [];
  for (let k = 0; k <= steps; k += 1) {
    const t = (k / steps) * 2 * Math.PI;
    ring.push(toLngLat(affine, [cx + radius * Math.cos(t), cy + radius * Math.sin(t)]));
  }
  return ring;
}

// The outer edge of a union of eps discs, as longitude/latitude polylines.
// Each disc contributes the arcs no other disc covers; where an arc ends, bisection finds
// the exact crossing with its neighbour, so the pieces meet without gaps or inner lines.
// `steps` matches circleRing so the edge sits on the filled discs.
export function unionEdge(affine, centers, eps, steps = 48) {
  const cell = 2 * eps;
  const grid = new Map();
  const keyOf = (x, y) => `${Math.floor(x / cell)},${Math.floor(y / cell)}`;
  centers.forEach(([x, y], i) => {
    const key = keyOf(x, y);
    if (!grid.has(key)) grid.set(key, []);
    grid.get(key).push(i);
  });
  const limit = eps * eps * (1 - 1e-9);
  const lines = [];
  const step = (2 * Math.PI) / steps;
  centers.forEach(([cx, cy], i) => {
    const gx = Math.floor(cx / cell);
    const gy = Math.floor(cy / cell);
    const others = [];
    for (let dx = -1; dx <= 1; dx += 1) {
      for (let dy = -1; dy <= 1; dy += 1) {
        for (const j of grid.get(`${gx + dx},${gy + dy}`) ?? []) {
          const [ox, oy] = centers[j];
          if (j === i || Math.hypot(ox - cx, oy - cy) >= 2 * eps) continue;
          if (ox === cx && oy === cy) {
            if (j < i) return; // an identical disc earlier in the list already drew this edge
            continue;
          }
          others.push(centers[j]);
        }
      }
    }
    const covered = (theta) => {
      const px = cx + eps * Math.cos(theta);
      const py = cy + eps * Math.sin(theta);
      return others.some(([ox, oy]) => (px - ox) ** 2 + (py - oy) ** 2 < limit);
    };
    const crossing = (a, b) => {
      const start = covered(a);
      for (let k = 0; k < 12; k += 1) {
        const mid = (a + b) / 2;
        if (covered(mid) === start) a = mid;
        else b = mid;
      }
      return (a + b) / 2;
    };
    const at = (theta) => toLngLat(affine, [cx + eps * Math.cos(theta), cy + eps * Math.sin(theta)]);
    const open = Array.from({ length: steps }, (_, k) => !covered(k * step));
    if (open.every(Boolean)) {
      lines.push(circleRing(affine, [cx, cy], eps, steps));
      return;
    }
    const first = open.indexOf(false);
    let run = null;
    for (let s = 1; s <= steps; s += 1) {
      const k = first + s;            // unwrapped index, so angles never jump back to 0
      const isOpen = open[k % steps];
      if (isOpen && !open[(k - 1) % steps]) run = [at(crossing((k - 1) * step, k * step))];
      if (isOpen) run.push(at(k * step));
      if (isOpen && !open[(k + 1) % steps]) {
        run.push(at(crossing(k * step, (k + 1) * step)));
        lines.push(run);
        run = null;
      }
    }
  });
  return lines;
}

const WINDS = ["east", "northeast", "north", "northwest", "west", "southwest", "south", "southeast"];
const SCREEN = ["right", "up and right", "up", "up and left", "left", "down and left", "down", "down and right"];

export function direction([dx, dy], kind) {
  const sector = (Math.round(Math.atan2(dy, dx) / (Math.PI / 4)) + 8) % 8;
  return (kind === "geo" ? WINDS : SCREEN)[sector];
}

export function distance(value, unit) {
  if (unit !== "m") return value.toFixed(2);
  if (value < 1000) return `${Math.round(value)} m`;
  return `${(value / 1000).toFixed(value < 100000 ? 1 : 0)} km`;
}

export function signed(value, unit) {
  const text = distance(Math.abs(value), unit);
  if (Math.abs(value) < (unit === "m" ? 0.5 : 0.005)) return unit === "m" ? "0 km" : "0.00";
  return `${value < 0 ? "−" : "+"}${text}`;
}

export function radius(value, unit) {
  if (unit !== "m") return value.toFixed(2);
  return `${(value / 1000).toFixed(value % 1000 === 0 ? 0 : 1)} km`;
}

export function latLonText([lng, lat]) {
  const ns = `${Math.abs(lat).toFixed(2)}° ${lat >= 0 ? "N" : "S"}`;
  const ew = `${Math.abs(lng).toFixed(2)}° ${lng >= 0 ? "E" : "W"}`;
  return `${ns}, ${ew}`;
}

export function formatDate(iso) {
  return new Date(`${iso}T00:00:00Z`).toLocaleDateString("en-GB", {
    day: "numeric", month: "short", year: "numeric", timeZone: "UTC",
  });
}

export const count = (n) => n.toLocaleString("en-US");
