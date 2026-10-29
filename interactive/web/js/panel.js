// The floating sheet: a dataset header, three tabs (Data, Cluster, Explain), and the page for the active tab.
import { count, direction, distance, formatDate, latLonText, radius, signed, toLngLat } from "./geometry.js";

const CHEVRON = '<svg width="11" height="7" viewBox="0 0 11 7" aria-hidden="true"><path d="M1 1l4.5 4.5L10 1" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/></svg>';
const CLOSE = '<svg width="10" height="10" viewBox="0 0 10 10" aria-hidden="true"><path d="M1.5 1.5l7 7M8.5 1.5l-7 7" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg>';
const CHECK = '<svg width="14" height="14" viewBox="0 0 14 14" aria-hidden="true"><path d="M2.5 7.5l3 3 6-7" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>';
const GLYPH = {
  core: '<svg width="12" height="12" viewBox="0 0 12 12" aria-hidden="true"><circle cx="6" cy="6" r="4.6" fill="#ff7a40" stroke="#0a0b0d" stroke-width="1"/></svg>',
  border: '<svg width="12" height="12" viewBox="0 0 12 12" aria-hidden="true"><circle cx="6" cy="6" r="4" fill="#16181c" stroke="#ff7a40" stroke-width="1.6"/></svg>',
  noise: '<svg width="12" height="12" viewBox="0 0 12 12" aria-hidden="true"><circle cx="6" cy="6" r="2.8" fill="#a6a6ac"/></svg>',
};
const ROLE_LABEL = { core: "Core point", border: "Border point", noise: "Noise" };
const TABS = [["data", "Data"], ["cluster", "Cluster"], ["explain", "Explain"]];

const escape = (text) => String(text).replace(/[&<>"']/g, (c) => `&#${c.charCodeAt(0)};`);
const plural = (n, [one, many]) => (n === 1 ? one : many);
const reducedMotion = () => window.matchMedia("(prefers-reduced-motion: reduce)").matches;

// Count a number up or down to `to` instead of jumping.
function tweenNumber(element, to, duration = 450) {
  const from = Number(element.dataset.value ?? to);
  element.dataset.value = to;
  const token = (element.tweenToken = (element.tweenToken ?? 0) + 1);
  if (from === to || reducedMotion()) {
    element.textContent = count(to);
    return;
  }
  const start = performance.now();
  const step = (now) => {
    if (token !== element.tweenToken) return;
    const t = Math.min(1, (now - start) / duration);
    element.textContent = count(Math.round(from + (to - from) * (1 - (1 - t) ** 3)));
    if (t < 1) requestAnimationFrame(step);
  };
  requestAnimationFrame(step);
}

function setNumber(element, value) {
  element.tweenToken = (element.tweenToken ?? 0) + 1;
  element.dataset.value = value;
  element.textContent = count(value);
}

// The dot size the map uses for a magnitude at regional zoom (see pointPaint in map.js).
const dotRadius = (mag) => 2.6 + Math.max(0, mag - 2) * 1.25;

export class Sheet {
  constructor(root, actions) {
    this.root = root;
    this.actions = actions;
    this.cardKey = null;
    root.addEventListener("click", (event) => {
      const target = event.target.closest("[data-action]");
      if (target && !target.disabled) actions[target.dataset.action]?.(target.dataset.value);
    });
    root.addEventListener("input", (event) => {
      if (event.target.id === "eps") actions.eps(Number(event.target.value));
      if (event.target.id === "minpts") actions.minPts(Number(event.target.value));
    });
    root.addEventListener("change", (event) => {
      if (event.target.id === "target") actions.target(Number(event.target.value));
    });
    document.addEventListener("click", (event) => {
      if (!event.target.closest(".head")) this.toggleMenu(false);
    });
    window.addEventListener("resize", () => this.placeThumb());
  }

  $(selector) {
    return this.root.querySelector(selector);
  }

  // The opening card. `returning` means the map has been visited and the button goes back to it.
  intro({ returning = false } = {}) {
    this.root.scrollTop = 0;
    this.root.innerHTML = `
      <div class="intro">
        <p class="course">COMP5331 · Group 1</p>
        <h1>Earthquake clusters, explained</h1>
        <p class="lede">In 2024, 1,260 earthquakes of magnitude 2 or more shook Southern California. See how DBSCAN groups them, why each one ends up where it does, and how far it would have to move to join another group.</p>
        <button type="button" class="primary" data-action="explore">${returning ? "Back to the map" : "Explore Southern California"}</button>
        <p class="credits">Data from the USGS earthquake catalog. DBSCAN after Ester et al. (1996), explanations after ExDBSCAN by Matthews et al. (2026).</p>
      </div>`;
  }

  ready() {
    const button = this.$('[data-action="explore"]');
    button.disabled = false;
    button.textContent = "Explore Southern California";
  }

  // Header and tabs for a dataset; the page below them is drawn by page().
  shell(state) {
    const d = state.dataset;
    this.root.scrollTop = 0;
    this.root.innerHTML = `
      <header class="head">
        <button type="button" class="dataset-button" data-action="menu" aria-haspopup="menu" aria-expanded="false">${escape(d.name)}${CHEVRON}</button>
        <p class="sub" id="sub">${escape(d.summary)}</p>
        <div class="menu" role="menu" hidden>${this.menuItems(state)}</div>
      </header>
      <nav class="segmented tabs" role="tablist" aria-label="Steps">
        <span class="thumb" aria-hidden="true"></span>
        ${TABS.map(([id, label]) => `<button type="button" role="tab" id="tab-${id}" data-action="tab" data-value="${id}">${label}</button>`).join("")}
      </nav>
      <div id="page" class="page"></div>`;
    const thumb = this.$(".tabs .thumb");
    thumb.style.transition = "none"; // the first placement should not slide in from the left edge
    this.tabs(state);
    void thumb.offsetWidth;
    thumb.style.transition = "";
  }

  tabs(state) {
    for (const [id] of TABS) {
      const tab = this.$(`#tab-${id}`);
      if (!tab) continue;
      tab.setAttribute("aria-selected", String(state.tab === id));
      tab.disabled = id === "explain" && !state.clustering;
    }
    this.activeTab = state.tab;
    this.placeThumb();
  }

  // Move the highlight under the active tab; it slides there by CSS transition.
  placeThumb() {
    const tab = this.$(`#tab-${this.activeTab}`);
    const thumb = this.$(".tabs .thumb");
    if (!tab || !thumb) return;
    thumb.style.width = `${tab.offsetWidth}px`;
    thumb.style.transform = `translateX(${tab.offsetLeft}px)`;
  }

  menuItems(state) {
    const item = (d) => `
      <button type="button" role="menuitemradio" aria-checked="${d.id === state.dataset.id}" data-action="dataset" data-value="${d.id}">
        <span><span class="item-name">${escape(d.name)}</span><span class="item-sub">${escape(d.summary)}</span></span>
        <span class="check">${d.id === state.dataset.id ? CHECK : ""}</span>
      </button>`;
    const real = state.datasets.filter((d) => d.kind === "geo");
    const shapes = state.datasets.filter((d) => d.kind !== "geo");
    return `<div class="menu-label">Real data</div>${real.map(item).join("")}
            <div class="menu-label">Synthetic shapes for teaching</div>${shapes.map(item).join("")}`;
  }

  toggleMenu(open) {
    const menu = this.$(".menu");
    if (!menu) return;
    const show = open ?? menu.hidden;
    menu.hidden = !show;
    this.$(".dataset-button").setAttribute("aria-expanded", String(show));
  }

  // Draw the active tab's page. `step` is +1 moving forward, -1 moving back, 0 to draw at once.
  // A move slides the old page out toward where it came from, slides the new one in from the other
  // side, and eases the sheet between the two heights.
  page(state, step = 0) {
    const page = this.$("#page");
    if (!page) return;
    this.tabs(state);
    const token = (this.pageToken = (this.pageToken ?? 0) + 1);
    const draw = () => {
      this.cardKey = null;
      if (state.tab === "data") page.innerHTML = this.dataPage(state);
      if (state.tab === "cluster") {
        page.innerHTML = this.clusterPage(state);
        this.params(state);
        if (state.clustering) this.summary(state);
        if (this.sliderTip) this.tipSliders(true);
      }
      if (state.tab === "explain") {
        page.innerHTML = this.explainPage(state);
        this.focus(state);
      }
    };
    if (step === 0 || reducedMotion()) {
      draw();
      return;
    }
    const before = this.root.offsetHeight;
    page.getAnimations().forEach((a) => a.cancel());
    const exit = page.animate(
      [{ opacity: 1, transform: "none" }, { opacity: 0, transform: `translateX(${-14 * step}px)` }],
      { duration: 140, easing: "ease-in", fill: "forwards" },
    );
    exit.finished.then(() => {
      if (token !== this.pageToken) return;
      draw();
      exit.cancel();
      this.root.scrollTop = 0;
      page.animate(
        [{ opacity: 0, transform: `translateX(${20 * step}px)` }, { opacity: 1, transform: "none" }],
        { duration: 360, easing: "cubic-bezier(0.2, 0.8, 0.2, 1)" },
      );
      const after = this.root.offsetHeight;
      if (Math.abs(after - before) > 1) {
        this.root.animate([{ height: `${before}px` }, { height: `${after}px` }], { duration: 360, easing: "cubic-bezier(0.2, 0.8, 0.2, 1)" });
      }
    }, () => {});
  }

  dataPage(state) {
    const d = state.dataset;
    const next = `<button type="button" class="primary" data-action="tab" data-value="cluster">${state.clustering ? "Show the clusters" : "Group them with DBSCAN"}</button>`;
    if (d.kind !== "geo") {
      return `
        <p class="lead-text">Each dot is one point of a synthetic shape. Shapes like this make DBSCAN's behaviour easy to see.</p>
        ${next}`;
    }
    const sizes = [2, 3, 4, 5].map((m) => {
      const r = dotRadius(m);
      const s = Math.ceil(2 * r + 2);
      return `<span><svg width="${s}" height="${s}" aria-hidden="true"><circle cx="${s / 2}" cy="${s / 2}" r="${r}" fill="rgba(235,235,240,0.9)" stroke="rgba(6,7,9,0.75)" stroke-width="0.8"/></svg>M${m}</span>`;
    }).join("");
    return `
      <p class="lead-text">Each dot is one earthquake recorded by USGS in 2024. Larger dots are stronger quakes.</p>
      <div class="size-legend" aria-label="Dot size by magnitude">${sizes}</div>
      <button type="button" class="link" data-action="replay">Replay 2024 in time order</button>
      ${next}`;
  }

  clusterPage(state) {
    const d = state.dataset;
    return `
      <div class="group" id="sliders">
        <label class="control">
          <span class="control-row"><span>Radius ε</span><output id="eps-out"></output></span>
          <input type="range" id="eps" aria-label="Radius" min="${d.eps.min}" max="${d.eps.max}" step="${d.eps.step}" value="${state.eps}">
        </label>
        <label class="control">
          <span class="control-row"><span>Neighbors needed</span><output id="minpts-out"></output></span>
          <input type="range" id="minpts" aria-label="Neighbors needed" min="${d.minPts.min}" max="${d.minPts.max}" step="1" value="${state.minPts}">
        </label>
      </div>
      <p class="tip" id="slider-tip" hidden>Drag either slider. The clusters update as you go.</p>
      <p class="hint" id="rule"></p>
      <button type="button" class="primary" data-action="run" id="run"${state.clustering ? " hidden" : ""}>Run DBSCAN</button>
      <div class="summary" id="summary"${state.clustering ? "" : " hidden"}>
        <div class="summary-head"><span class="big" id="n-clusters">0</span><span class="unit" id="clusters-unit">clusters</span></div>
        <ul class="legend">
          <li>${GLYPH.core}<b id="n-core">0</b>core</li>
          <li>${GLYPH.border}<b id="n-border">0</b>border</li>
          <li>${GLYPH.noise}<b id="n-noise">0</b>noise</li>
        </ul>
        <p class="hint" id="summary-hint"></p>
      </div>`;
  }

  explainPage(state) {
    return `
      <p class="hint compact" id="compact"></p>
      <div id="pick"></div>
      <section class="step" id="step-change" hidden>
        <h2>What would change it?</h2>
        <div id="change" class="step"></div>
      </section>`;
  }

  // A one-time tip on the sliders: the group's outline breathes a few times and a short line explains
  // that dragging updates the map. Turning it off fades the line away.
  tipSliders(on) {
    this.sliderTip = on;
    const group = this.$("#sliders");
    const tip = this.$("#slider-tip");
    if (!group || !tip) return;
    if (on) {
      tip.hidden = false;
      tip.classList.remove("gone");
      group.classList.remove("breathe");
      void group.offsetWidth; // restart the breathing outline
      group.classList.add("breathe");
      return;
    }
    group.classList.remove("breathe");
    tip.classList.add("gone");
    setTimeout(() => { if (!this.sliderTip) tip.hidden = true; }, 300);
  }

  // The line under the dataset name: the summary, or the date being replayed.
  replay(state, date) {
    const sub = this.$("#sub");
    if (sub) sub.textContent = date ? `Replaying 2024 · ${formatDate(date).replace(/ \d{4}$/, "")}` : state.dataset.summary;
  }

  params(state) {
    const d = state.dataset;
    const eps = this.$("#eps");
    if (eps) {
      for (const input of [eps, this.$("#minpts")]) {
        input.style.setProperty("--pct", `${((input.value - input.min) / (input.max - input.min)) * 100}%`);
      }
      this.$("#eps-out").textContent = radius(state.eps, d.unit);
      this.$("#minpts-out").textContent = state.minPts;
      this.$("#rule").textContent =
        `A ${d.noun[0]} becomes a core point when at least ${state.minPts} ${d.noun[1]}, itself included, lie within ${radius(state.eps, d.unit)} of it.`;
    }
    this.compact(state);
  }

  // The settings behind the Explain page, with a way back to change them.
  compact(state) {
    const line = this.$("#compact");
    if (!line) return;
    const c = state.clustering?.counts;
    const clusters = c ? ` · ${count(c.clusters)} ${plural(c.clusters, ["cluster", "clusters"])}` : "";
    line.innerHTML = `Radius ${radius(state.eps, state.dataset.unit)}, ${state.minPts} neighbors needed${clusters}
      <button type="button" class="link" data-action="tab" data-value="cluster">Change</button>`;
  }

  // Show the clustering summary. `live` starts the counters at zero for liveCounts() to drive.
  summary(state, { live = false } = {}) {
    const box = this.$("#summary");
    if (!box) return;
    const d = state.dataset;
    const c = state.clustering.counts;
    this.$("#run").hidden = true;
    if (box.hidden) {
      box.hidden = false;
      box.classList.add("enter");
    }
    const numbers = { clusters: this.$("#n-clusters"), core: this.$("#n-core"), border: this.$("#n-border"), noise: this.$("#n-noise") };
    for (const [key, element] of Object.entries(numbers)) {
      if (live) setNumber(element, 0);
      else tweenNumber(element, c[key]);
    }
    this.$("#clusters-unit").textContent = plural(c.clusters, ["cluster", "clusters"]);
    this.$("#summary-hint").textContent =
      `Each cluster reaches ${radius(state.eps, d.unit)} around its core points, ${d.kind === "geo" ? "outlined on the map when you zoom in" : "shown as the outlined area"}. Click any ${d.noun[0]} to see why it is core, border or noise.`;
  }

  liveCounts(counts) {
    if (!this.$("#n-clusters")) return;
    setNumber(this.$("#n-clusters"), counts.clusters);
    setNumber(this.$("#n-core"), counts.core);
    setNumber(this.$("#n-border"), counts.border);
    setNumber(this.$("#n-noise"), counts.noise);
    this.$("#clusters-unit").textContent = plural(counts.clusters, ["cluster", "clusters"]);
  }

  // The Explain page: the selected point's card, then what would change it.
  focus(state) {
    const pick = this.$("#pick");
    if (!pick) return;
    const change = this.$("#step-change");
    this.compact(state);
    if (!state.focus || !state.why) {
      const d = state.dataset;
      this.cardKey = null;
      pick.innerHTML = `<p class="hint">Click any ${d.noun[0]} on the map to see why it is core, border or noise. Click an empty spot to test an imagined one.</p>`;
      change.hidden = true;
      return;
    }
    const key = state.focus.kind === "point" ? `p${state.focus.index}` : `s${state.focus.xy.join(",")}`;
    const why = state.why;
    const met = why.count >= state.minPts;
    const d = state.dataset;
    const meterText = `${why.count} of ${state.minPts} needed within ${radius(state.eps, d.unit)}`;
    const width = `${Math.min(1, why.count / state.minPts) * 100}%`;
    if (key === this.cardKey) {
      // Same selection, new parameters: update in place so the chip and meter animate.
      const chip = this.$(".card .chip");
      chip.className = `chip chip-${why.role}`;
      chip.innerHTML = `${GLYPH[why.role]}${ROLE_LABEL[why.role]}`;
      this.$(".card .reason").textContent = this.reason(state);
      const fill = this.$(".card .meter-fill");
      fill.classList.toggle("met", met);
      fill.style.width = width;
      this.$(".card .meter-text").textContent = meterText;
    } else {
      this.cardKey = key;
      const { title, sub } = this.identity(state);
      pick.innerHTML = `
        <div class="card enter">
          <div class="card-head">
            <div><div class="card-title">${escape(title)}</div><div class="card-sub">${escape(sub)}</div></div>
            <button type="button" class="icon-button" data-action="clear" aria-label="Clear selection">${CLOSE}</button>
          </div>
          <span class="chip chip-${why.role}">${GLYPH[why.role]}${ROLE_LABEL[why.role]}</span>
          <p class="reason">${escape(this.reason(state))}</p>
          <div class="meter" aria-hidden="true">
            <div class="meter-track"><div class="meter-fill${met ? " met" : ""}" style="width:0%"></div></div>
            <div class="meter-text">${meterText}</div>
          </div>
        </div>`;
      requestAnimationFrame(() => { const fill = this.$(".card .meter-fill"); if (fill) fill.style.width = width; });
    }
    if (change.hidden) {
      change.hidden = false;
      change.classList.add("enter");
    }
    this.change(state);
  }

  identity(state) {
    const d = state.dataset;
    const f = state.focus;
    const xy = state.why.point;
    if (f.kind === "point" && d.kind === "geo") {
      const m = state.points.meta[f.index];
      return { title: `M ${m.mag.toFixed(1)} · ${formatDate(m.date)}`, sub: m.place };
    }
    if (f.kind === "point") return { title: `Point ${f.index + 1}`, sub: `x ${xy[0].toFixed(2)}, y ${xy[1].toFixed(2)}` };
    if (d.kind === "geo") return { title: "Imagined earthquake", sub: latLonText(toLngLat(d.affine, xy)) };
    return { title: "Imagined point", sub: `x ${xy[0].toFixed(2)}, y ${xy[1].toFixed(2)}` };
  }

  reason(state) {
    const d = state.dataset;
    const w = state.why;
    const [one, many] = d.noun;
    const e = radius(state.eps, d.unit);
    const name = (id) => state.names[id];
    const near = w.nearestCore ? ` The nearest, in ${name(w.nearestCore.cluster)}, is ${distance(w.nearestCore.distance, d.unit)} away.` : "";
    const within = w.count === 1 ? `No other ${many} lie within ${e}` : `Only ${w.count} ${many} lie within ${e}, counting itself`;
    if (state.focus.kind === "point") {
      if (w.role === "core") {
        return `${w.count} ${many} lie within ${e} of it, counting itself. That meets the ${state.minPts} needed, so it anchors ${name(w.cluster)}.`;
      }
      if (w.role === "border") {
        return `${within}, short of the ${state.minPts} needed. It still belongs to ${name(w.cluster)} because one of that cluster's core points is ${distance(w.host.distance, d.unit)} away, inside the ${e} radius.`;
      }
      return `${within}, short of the ${state.minPts} needed, and no core point is that close.${near}`;
    }
    if (w.role === "core") {
      const joins = w.cluster !== null ? ` It would join ${name(w.cluster)}.` : " It would start a new cluster with its neighbors.";
      return `A ${one} here would have ${w.count} ${many} within ${e}, counting itself, enough for a core point.${joins}`;
    }
    if (w.role === "border") {
      return `A ${one} here would have only ${w.count} ${plural(w.count, d.noun)} within ${e}, but it would sit ${distance(w.host.distance, d.unit)} from a core point of ${name(w.cluster)}, so it would join that cluster as a border point.`;
    }
    return `A ${one} here would be noise: only ${w.count} ${plural(w.count, d.noun)} within ${e}, counting itself, and no core point is that close.${near}`;
  }

  // `scroll` brings a new answer into view; `fresh` plays its entrance.
  change(state, { scroll = false, fresh = false } = {}) {
    const box = this.$("#change");
    if (!box || !state.why) return;
    const d = state.dataset;
    const targets = state.why.targets;
    if (!targets.length) {
      box.innerHTML = '<p class="hint">There is no other cluster to join.</p>';
      return;
    }
    const options = targets.map((t) =>
      `<option value="${t.cluster}"${t.cluster === state.target ? " selected" : ""}>${escape(t.name)} · ${t.gap > 0 ? `${distance(t.gap, d.unit)} away` : "in reach"}</option>`).join("");
    const segments = [{ fixed: null, label: "Any" }, ...d.moves].map((m) =>
      `<button type="button" role="radio" aria-checked="${m.fixed === state.fixed}" data-action="fixed" data-value="${m.fixed ?? "any"}">${escape(m.label)}</button>`).join("");
    box.innerHTML = `
      <div class="group">
        <label class="field"><span>Join</span><select id="target" aria-label="Cluster to join">${options}</select></label>
        <div class="field field-stack"><span>Direction</span><div class="segmented" role="radiogroup" aria-label="Direction the point may move">${segments}</div></div>
      </div>
      ${state.answer ? this.answer(state, fresh) : '<button type="button" class="primary" data-action="move">Show the smallest move</button>'}
      ${state.error ? `<p class="error">${escape(state.error)}</p>` : ""}`;
    if (scroll && state.answer) box.lastElementChild?.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }

  answer(state, fresh) {
    const d = state.dataset;
    const a = state.answer;
    const e = radius(state.eps, d.unit);
    const target = escape(state.names[a.target]);
    const open = `<div class="answer${fresh ? " enter" : ""}">`;
    if (a.status === "already_reachable") {
      return `${open}<div class="answer-head">No move needed</div><p>It is already within ${e} of a core point in ${target}.</p></div>`;
    }
    if (!a.counterfactual) {
      const how = d.moves.find((m) => m.fixed === a.fixed)?.label.toLowerCase();
      const text = a.fixed !== null ? `Moving only ${how}, it never comes within ${e} of a core point in ${target}.` : `${target} has no core point it can reach.`;
      return `${open}<div class="answer-head">Out of reach</div><p>${text}</p></div>`;
    }
    const axes = d.kind === "geo" ? ["East", "North"] : ["x", "y"];
    const detail = a.change.map((value, axis) => `${axes[axis]} ${a.fixed === axis ? "unchanged" : signed(value, d.unit)}`).join(" · ");
    let check = '<button type="button" class="link" data-action="verify">Check by re-running DBSCAN</button>';
    if (state.verify) {
      const v = state.verify;
      const others = v.changedRoles ? ` ${v.changedRoles} other ${plural(v.changedRoles, d.noun)} changed role.` : ` No other ${d.noun[0]} changed role.`;
      const text = v.joined
        ? `Re-running DBSCAN with the moved ${d.noun[0]} puts it in ${target} as a ${v.role} point.${others}`
        : `Re-running DBSCAN leaves it as ${v.role}.`;
      check = `<div class="verify enter">${CHECK}<span>${text}</span></div>`;
    }
    return `${open}
        <div class="answer-head">${distance(a.distance, d.unit)} <span class="muted">${direction(a.change, d.kind)}</span></div>
        <p>That puts it just inside the ${e} radius of a core point in ${target}, so DBSCAN would count it in that cluster.</p>
        <div class="answer-detail">${detail}</div>
        ${check}
      </div>`;
  }

  busy(on) {
    for (const button of this.root.querySelectorAll('[data-action="move"], [data-action="verify"], [data-action="run"]')) {
      button.disabled = on;
    }
  }
}
