// App state and navigation. After the globe intro, three tabs (Data, Cluster, Explain) can be visited
// in any order; the map follows the active tab, and nothing computed so far is thrown away.
import * as api from "./api.js";
import { distance, formatDate, toData } from "./geometry.js";
import { ExplorerMap } from "./map.js";
import { Sheet } from "./panel.js";

const TAB_ORDER = ["data", "cluster", "explain"];

const state = {
  datasets: [],
  dataset: null,
  points: null,
  eps: 0,
  minPts: 0,
  stage: "intro",        // intro (globe) or map
  visited: false,        // whether the map has been shown once, so the intro offers a way back
  tab: "data",
  clustering: null,
  names: {},
  focus: null,           // { kind: "point", index } or { kind: "spot", xy }
  focusEps: null,        // the eps the focus circle is drawn with
  why: null,
  target: null,
  fixed: null,           // the coordinate a move must keep: null (any direction), 0 (east or x) or 1 (north or y)
  answer: null,
  verify: null,
  error: null,
  // One-time tips: pending → shown → done. The slider tip follows the first run; the map callout
  // follows the first slider change (or a pause), and both end once a point is clicked.
  tips: { sliders: "pending", map: "pending" },
  tipPoint: null,
};
let tipTimer;

const sheetElement = document.getElementById("sheet");
const tooltip = document.getElementById("tooltip");
const controls = document.getElementById("map-controls");
const globeButton = controls.querySelector('[data-action="globe"]');
const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
let explorer;
const tickets = { cluster: 0, focus: 0, answer: 0 };

const sheet = new Sheet(sheetElement, {
  explore,
  tab: goTab,
  replay: replayYear,
  run: () => runClustering(true),
  menu: () => sheet.toggleMenu(),
  dataset: switchDataset,
  eps: (value) => setParam("eps", value),
  minPts: (value) => setParam("minPts", value),
  clear: clearFocus,
  move: () => showMove(),
  verify: verifyMove,
  target: (cluster) => {
    state.target = cluster;
    explorer.setTarget(cluster);
    if (state.answer) showMove();
  },
  fixed: (value) => {
    state.fixed = value === "any" ? null : Number(value);
    if (state.answer) showMove();
    else sheet.change(state);
  },
});

const request = () => ({ dataset: state.dataset.id, eps: state.eps, minPts: state.minPts });
const query = () => (state.focus.kind === "point" ? { index: state.focus.index } : { point: state.focus.xy });
const allRoles = (role) => state.points.xy.map(() => role);

async function init() {
  const [datasets, map] = await Promise.all([
    api.getDatasets(),
    ExplorerMap.create(document.getElementById("map"), sheetElement, { hover, click }),
  ]);
  explorer = map;
  explorer.map.on("movestart", () => { tooltip.hidden = true; });
  state.datasets = datasets;
  await explorer.ready;
  await loadDataset("usgs");
  if (!reducedMotion) explorer.spin();
  sheet.ready();
}

async function loadDataset(id) {
  tickets.cluster += 1;
  state.dataset = state.datasets.find((d) => d.id === id);
  state.points = await api.getPoints(id);
  state.eps = state.dataset.eps.default;
  state.minPts = state.dataset.minPts.default;
  state.clustering = null;
  state.names = {};
  resetFocus();
  explorer.setDataset(state.dataset, state.points);
}

// From the globe to the map. The first visit replays 2024; a return restores the tab you left.
async function explore() {
  const returning = state.visited;
  state.visited = true;
  state.stage = "map";
  sheet.shell(state);
  sheet.page(state);
  controls.hidden = false;
  globeButton.hidden = state.dataset.kind !== "geo";
  await explorer.flyTo(state.dataset.bounds, reducedMotion ? 0 : returning ? 3600 : 5200);
  explorer.showScale(state.dataset.kind === "geo");
  if (returning) applyTab();
  else await revealPoints();
}

async function goGlobe() {
  tooltip.hidden = true;
  hideMapTip(false);
  state.stage = "intro";
  controls.hidden = true;
  explorer.showOverlays(false);
  explorer.setReach(null);
  explorer.setClusterNames(null);
  explorer.showScale(false);
  explorer.setRoles(allRoles(-2), { duration: 300 });
  sheet.intro({ returning: true });
  await explorer.flyGlobe();
  if (state.stage === "intro" && !reducedMotion) explorer.spin();
}

function goTab(tab) {
  if (tab === state.tab || (tab === "explain" && !state.clustering)) return;
  const step = Math.sign(TAB_ORDER.indexOf(tab) - TAB_ORDER.indexOf(state.tab));
  state.tab = tab;
  sheet.toggleMenu(false);
  sheet.page(state, step);
  applyTab();
  if (tab !== "cluster") hideMapTip(false);
  else if (state.tips.sliders !== "pending") scheduleMapTip(900);
}

// Make the map show what the active tab is about: raw quakes on Data, the clustering (and any
// selection) on Cluster and Explain. Every change animates.
function applyTab() {
  const clustered = state.tab !== "data" && Boolean(state.clustering);
  explorer.setRoles(clustered ? state.clustering.roles : allRoles(-1));
  explorer.setReach(clustered ? state.clustering : null, state.eps);
  explorer.setClusterNames(clustered ? state.clustering : null);
  explorer.showOverlays(clustered && Boolean(state.focus));
  explorer.setDim(state.clustering?.labels ?? [], clustered && state.answer ? state.answer.target : null);
}

// Points appear in data order. The USGS file is in time order, so this replays 2024 in two seconds.
async function revealPoints() {
  const n = state.points.xy.length;
  const order = state.points.xy.map((_, i) => i);
  const meta = state.points.meta;
  await explorer.setRoles(allRoles(-1), {
    order,
    total: meta ? 2200 : 700,
    duration: 380,
    onProgress: meta ? (k) => sheet.replay(state, meta[Math.min(n, k) - 1]?.date) : null,
  });
  sheet.replay(state, null);
}

async function replayYear() {
  if (state.tab !== "data") return;
  await explorer.setRoles(allRoles(-2), { duration: 260 });
  await revealPoints();
}

async function switchDataset(id) {
  sheet.toggleMenu(false);
  if (id === state.dataset.id) return;
  tooltip.hidden = true;
  hideMapTip(false);
  explorer.clearFocus();
  explorer.setReach(null);
  explorer.setClusterNames(null);
  await explorer.setRoles(allRoles(-2), { duration: 280 });
  await loadDataset(id);
  state.tab = "data";
  sheet.shell(state);
  sheet.page(state);
  explorer.fit(state.dataset.bounds, { duration: 0 });
  explorer.showScale(state.dataset.kind === "geo");
  globeButton.hidden = state.dataset.kind !== "geo";
  await revealPoints();
}

let paramTimer;
function setParam(key, value) {
  state[key] = value;
  sheet.params(state);
  endSliderTip();
  if (state.clustering) {
    clearTimeout(paramTimer);
    paramTimer = setTimeout(() => runClustering(false), 80);
    if (state.tips.map === "pending") scheduleMapTip(1400);
  }
}

function endSliderTip() {
  if (state.tips.sliders !== "shown") return;
  state.tips.sliders = "done";
  sheet.tipSliders(false);
}

// The map callout goes on a noise point just outside a cluster's reach (the most telling case), with
// room on screen for the pill above it, preferring quakes big enough to hit easily. Without such
// noise it falls back to a border point, then a core point.
function pickTipPoint() {
  const { roles, clusters } = state.clustering;
  const { xy, meta } = state.points;
  const cores = clusters.flatMap((cluster) => cluster.core);
  for (const role of [2, 1, 0]) {
    let best = null;
    roles.forEach((r, i) => {
      if (r !== role || !explorer.inView(xy[i], { top: 90, side: 150 })) return;
      const small = Boolean(meta) && meta[i].mag < 2.6;
      let gap = Infinity;
      for (const j of cores) if (j !== i) gap = Math.min(gap, Math.hypot(xy[j][0] - xy[i][0], xy[j][1] - xy[i][1]));
      if (!best || small < best.small || (small === best.small && gap < best.gap)) best = { index: i, small, gap };
    });
    if (best) return best.index;
  }
  return null;
}

const tipText = (role) => `Click to see why it's ${["a core point", "a border point", "noise"][role]}`;

function scheduleMapTip(delay) {
  clearTimeout(tipTimer);
  tipTimer = setTimeout(showMapTip, delay);
}

// One tip at a time: the callout replaces the slider tip if that is still showing.
function showMapTip() {
  if (state.tips.map !== "pending" || state.tab !== "cluster" || state.focus || !state.clustering || state.stage !== "map") return;
  const index = pickTipPoint();
  if (index === null) return;
  state.tips.map = "shown";
  state.tipPoint = index;
  endSliderTip();
  explorer.showCoach(state.points.xy[index], tipText(state.clustering.roles[index]), () => click(index, null));
}

// `done` retires the callout for good (a point was clicked); otherwise it can come back later.
function hideMapTip(done) {
  clearTimeout(tipTimer);
  explorer.hideCoach();
  if (done) state.tips.map = "done";
  else if (state.tips.map === "shown") state.tips.map = "pending";
}

// Running totals after the first k points of DBSCAN's expansion order.
function runningTally(result) {
  const steps = [{ clusters: 0, core: 0, border: 0, noise: 0 }];
  const seen = new Set();
  const tally = { clusters: 0, core: 0, border: 0, noise: 0 };
  for (const i of result.order) {
    const label = result.labels[i];
    if (label >= 0 && !seen.has(label)) {
      seen.add(label);
      tally.clusters += 1;
    }
    tally[["core", "border", "noise"][result.roles[i]]] += 1;
    steps.push({ ...tally });
  }
  return (k) => steps[Math.min(k, steps.length - 1)];
}

// `animate` plays the first run: points take their roles in expansion order while the counters climb.
// Later runs (slider changes) recolour only the points that changed and cross-fade the reach.
async function runClustering(animate) {
  const ticket = ++tickets.cluster;
  sheet.busy(true);
  let result;
  try {
    result = await api.cluster(request());
  } catch (error) {
    return fail(error);
  } finally {
    sheet.busy(false);
  }
  if (ticket !== tickets.cluster) return;
  state.clustering = result;
  state.names = Object.fromEntries(result.clusters.map((c) => [c.id, c.name]));
  sheet.tabs(state);
  const onMap = state.tab !== "data";
  if (animate && onMap) {
    sheet.summary(state, { live: true });
    const tally = runningTally(result);
    let reachShown = false;
    await explorer.setRoles(result.roles, {
      order: result.order,
      total: 2400,
      duration: 480,
      onProgress: (k) => {
        if (ticket !== tickets.cluster) return;
        sheet.liveCounts(tally(k));
        if (!reachShown && k >= result.order.length * 0.6) {
          reachShown = true;
          explorer.setReach(result, state.eps);
        }
      },
    });
    if (ticket !== tickets.cluster) return;
    if (!reachShown) explorer.setReach(result, state.eps);
    explorer.setClusterNames(result);
    // The slider tip comes first; the map callout follows a slider change, or a pause.
    if (state.tips.sliders === "pending") {
      state.tips.sliders = "shown";
      sheet.tipSliders(true);
      scheduleMapTip(7000);
    } else scheduleMapTip(1200);
  } else if (onMap) {
    explorer.setRoles(result.roles);
    explorer.setReach(result, state.eps);
    explorer.setClusterNames(result);
    // The callout stays on its point; only its words follow the point's new role.
    if (state.tips.map === "shown") explorer.coachText(tipText(result.roles[state.tipPoint]));
  }
  sheet.summary(state);
  if (state.focus) await refreshFocus(false);
  else sheet.focus(state);
}

function click(index, lngLat) {
  if (state.stage !== "map" || !state.clustering) return;
  tooltip.hidden = true;
  hideMapTip(true);
  endSliderTip();
  sheet.toggleMenu(false);
  resetFocus();
  state.focus = index === null ? { kind: "spot", xy: toData(state.dataset.affine, lngLat) } : { kind: "point", index };
  goTab("explain");
  refreshFocus(true);
}

// `reveal` is a new selection: grow its circle and frame it. Otherwise parameters changed: resize in place.
async function refreshFocus(reveal) {
  const ticket = ++tickets.focus;
  let why;
  try {
    why = await api.why({ ...request(), ...query() });
  } catch (error) {
    return fail(error);
  }
  if (ticket !== tickets.focus || !state.focus) return;
  state.why = why;
  if (!why.targets.some((t) => t.cluster === state.target)) state.target = why.targets[0]?.cluster ?? null;
  const anchor = why.role === "border" ? why.host : why.role === "noise" ? why.nearestCore : null;
  const link = anchor ? { to: state.points.xy[anchor.index], text: distance(anchor.distance, state.dataset.unit) } : null;
  const fromEps = reveal ? null : state.focusEps;
  state.focusEps = state.eps;
  explorer.showFocus({ point: why.point, eps: state.eps, neighbors: why.neighbors, link, fromEps });
  if (reveal) explorer.frame(link ? [why.point, link.to] : [why.point], state.eps * (link ? 1.3 : 2.2));
  sheet.focus(state);
  if (state.answer) await showMove({ follow: reveal });
  else {
    explorer.setTarget(null);
    explorer.setDim(state.clustering.labels, null);
  }
}

// `follow` frames the answer and scrolls the sheet to it; slider-driven updates leave both in place
// and slide the route's end from where it was.
async function showMove({ follow = true } = {}) {
  if (state.target === null || !state.focus) return;
  const ticket = ++tickets.answer;
  const previous = state.answer?.counterfactual ?? null;
  const fresh = !state.answer || follow;
  sheet.busy(true);
  let answer;
  try {
    answer = await api.explain({ ...request(), ...query(), target: state.target, fixed: state.fixed });
  } catch (error) {
    return fail(error);
  } finally {
    sheet.busy(false);
  }
  if (ticket !== tickets.answer || !state.focus) return;
  state.answer = answer;
  state.verify = null;
  state.error = null;
  explorer.setTarget(answer.target);
  explorer.setDim(state.clustering.labels, answer.target);
  if (answer.counterfactual) {
    explorer.showAnswer({
      original: answer.original, counterfactual: answer.counterfactual, reference: answer.reference.point,
      eps: state.eps, label: distance(answer.distance, state.dataset.unit), previous: follow ? null : previous,
    });
    if (follow) explorer.frame([answer.original, answer.counterfactual, answer.reference.point], state.eps * 1.3);
  } else {
    const allowed = answer.fixed === null ? null : { fixed: answer.fixed, value: answer.original[answer.fixed] };
    explorer.showAnswer({ allowed, bounds: state.dataset.bounds });
  }
  sheet.change(state, { scroll: follow, fresh });
}

async function verifyMove() {
  const answer = state.answer;
  if (!answer?.counterfactual) return;
  sheet.busy(true);
  try {
    state.verify = await api.verify({
      ...request(), ...query(), counterfactual: answer.counterfactual, reference: answer.reference.index, fixed: answer.fixed,
    });
  } catch (error) {
    return fail(error);
  } finally {
    sheet.busy(false);
  }
  sheet.change(state);
}

function resetFocus() {
  tickets.focus += 1;
  tickets.answer += 1;
  Object.assign(state, { focus: null, focusEps: null, why: null, target: null, answer: null, verify: null, error: null });
}

function clearFocus() {
  resetFocus();
  explorer.clearFocus();
  if (state.clustering) explorer.setDim(state.clustering.labels, null);
  sheet.focus(state);
}

function fail(error) {
  console.error(error);
  state.error = error.message;
  if (state.why) sheet.change(state);
}

const escape = (text) => String(text).replace(/[&<>"']/g, (c) => `&#${c.charCodeAt(0)};`);

function hover(index, event) {
  if (index === null || state.stage !== "map") {
    tooltip.hidden = true;
    return;
  }
  const d = state.dataset;
  const lines = [];
  if (d.kind === "geo") {
    const m = state.points.meta[index];
    lines.push(`<div class="t-title">M ${m.mag.toFixed(1)} · ${formatDate(m.date)}</div>`, `<div class="t-sub">${escape(m.place)}</div>`);
  } else {
    const [x, y] = state.points.xy[index];
    lines.push(`<div class="t-title">Point ${index + 1}</div>`, `<div class="t-sub">x ${x.toFixed(2)}, y ${y.toFixed(2)}</div>`);
  }
  if (state.clustering && state.tab !== "data") {
    const role = state.clustering.roles[index];
    const name = state.names[state.clustering.labels[index]];
    lines.push(`<div class="t-sub">${role === 2 ? "Noise" : `${role === 0 ? "Core" : "Border"} · ${escape(name)}`}</div>`);
  }
  tooltip.innerHTML = lines.join("");
  tooltip.hidden = false;
  const box = tooltip.getBoundingClientRect();
  tooltip.style.left = `${Math.min(event.clientX + 14, window.innerWidth - box.width - 8)}px`;
  tooltip.style.top = `${event.clientY + 16 + box.height > window.innerHeight ? event.clientY - box.height - 12 : event.clientY + 16}px`;
}

controls.addEventListener("click", (event) => {
  const action = event.target.closest("[data-action]")?.dataset.action;
  if (action === "globe") goGlobe();
  if (action === "zoom-in") explorer.zoom(1);
  if (action === "zoom-out") explorer.zoom(-1);
  if (action === "fit") explorer.fit(state.dataset.bounds);
});

document.addEventListener("keydown", (event) => {
  if (event.key !== "Escape") return;
  sheet.toggleMenu(false);
  if (state.focus) clearFocus();
});

init().catch((error) => {
  console.error(error);
  const button = sheetElement.querySelector('[data-action="explore"]');
  if (button) button.textContent = "Could not load the data. Is the server running?";
});
