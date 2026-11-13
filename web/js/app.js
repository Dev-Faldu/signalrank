(function () {
  "use strict";
  const $ = (s, r) => (r || document).querySelector(s);
  const $$ = (s, r) => Array.from((r || document).querySelectorAll(s));
  const fmt = (n, d) => Number(n).toLocaleString("en-US", { maximumFractionDigits: d == null ? 0 : d, minimumFractionDigits: d == null ? 0 : d });
  const pct = (x, d) => (x * 100).toFixed(d == null ? 0 : d) + "%";
  const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

  const CAMEO = { "01": "Public statement", "02": "Appeal", "03": "Intent to cooperate", "04": "Consult", "05": "Diplomatic cooperation", "06": "Material cooperation", "07": "Provide aid", "08": "Yield", "09": "Investigate", "10": "Demand", "11": "Disapprove", "12": "Reject", "13": "Threaten", "14": "Protest", "15": "Show of force", "16": "Reduce relations", "17": "Coerce", "18": "Assault", "19": "Fight", "20": "Mass violence" };
  const FIPS = { US: "United States", UK: "United Kingdom", IN: "India", RS: "Russia", NI: "Nigeria", CH: "China", IS: "Israel", UP: "Ukraine", PK: "Pakistan", AS: "Australia", CA: "Canada", GM: "Germany", FR: "France", IR: "Iran", SF: "South Africa", BR: "Brazil", MX: "Mexico", JA: "Japan", KS: "South Korea", TU: "Turkey", EG: "Egypt", SA: "Saudi Arabia", IT: "Italy", SP: "Spain", PL: "Poland", ID: "Indonesia", RP: "Philippines", BG: "Bangladesh", KE: "Kenya", UG: "Uganda", NO: "Norway", AF: "Afghanistan", IZ: "Iraq", SY: "Syria", LE: "Lebanon", GZ: "Gaza Strip", WE: "West Bank", NA: "Unspecified", OTHER: "Other" };
  const cname = (c) => FIPS[c] || c;
  const QUAD = (t) => { const n = +t; return n <= 4 ? 1 : n <= 8 ? 2 : n <= 13 ? 3 : 4; };

  let SNAP, MODEL, WORLD;
  const S = { shown: 40, sel: null };

  function loadAll() {
    // Production: one gzipped bundle (small, fast). Local dev: plain JSON files.
    const viaBundle = fetch("data/bundle.bin").then((r) => { if (!r.ok || !window.DecompressionStream) throw new Error("no bundle"); return new Response(r.body.pipeThrough(new DecompressionStream("gzip"))).json(); })
      .then((b) => [b.snapshot, b.model, b.world]);
    return viaBundle.catch(() => Promise.all(["data/snapshot.json", "data/model.json", "data/world.json"].map((u) => fetch(u).then((r) => r.json()))));
  }
  loadAll().then((d) => { SNAP = d[0]; MODEL = d[1]; WORLD = d[2]; init(); })
    .catch((e) => { $("#asofText").textContent = "Could not load data"; console.error(e); });

  /* ---------- helpers ---------- */
  function host(u) { try { return new URL(u).hostname.replace(/^www\./, ""); } catch (e) { return u; } }
  function headline(u) {
    try {
      const p = new URL(u).pathname.split("/").filter(Boolean);
      let best = "";
      p.forEach((seg) => {
        let t = decodeURIComponent(seg).replace(/\b\d{5,}\b\.?/g, " ").replace(/\.(html?|php|aspx?|cms|ece|amp)$/i, "").replace(/[-_+]+/g, " ");
        t = t.split(/\s+/).filter((w) => /[a-z]/i.test(w) && !/^[0-9a-f]{6,}$/i.test(w) && w.length < 20).join(" ").replace(/^[^a-z0-9]+/i, "").trim();
        if (t.split(" ").length >= 3 && t.length > best.length) best = t;
      });
      if (!best) return "Story on " + host(u);
      return best.charAt(0).toUpperCase() + best.slice(1);
    } catch (e) { return u; }
  }
  const col = (p) => (p >= SNAP.threshold ? "#10b981" : p >= 0.35 ? "#6366f1" : "#94a3b8");
  const when = (t) => { const d = new Date(t.replace(" ", "T") + ":00Z"); return d.toLocaleString("en-US", { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit", timeZone: "UTC", hour12: false }) + " UTC"; };
  function bars(el, rows, opts) {
    opts = opts || {};
    const mx = Math.max.apply(null, rows.map((r) => r.v)) || 1;
    el.innerHTML = rows.map((r) => `<div class="hb"><span title="${esc(r.l)}">${esc(r.l)}</span><div class="bar"><i style="width:${(r.v / mx) * 100}%;${r.c ? "background:" + r.c : ""}"></i></div><em>${r.t != null ? r.t : fmt(r.v)}</em></div>`).join("");
  }

  /* ---------- init ---------- */
  function init() {
    const d = new Date(SNAP.as_of.replace(" ", "T") + "Z");
    $("#asofText").textContent = "Snapshot · " + d.toLocaleString("en-US", { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit", timeZone: "UTC", hour12: false }) + " UTC · scored in your browser";
    $("#fChamp").textContent = SNAP.champion;
    kpis(); filters(); tabs(); renderList(); trends(); model(); mapInit(); tryInit();
    const h = location.hash.replace("#", ""); if (h && $("#v-" + h)) go(h);
  }

  function kpis() {
    const m = SNAP.metrics.find((x) => x.model === SNAP.champion) || SNAP.metrics[0];
    const b = SNAP.metrics.find((x) => x.model === "baseline_src_1h");
    const ds = SNAP.data_size;
    const cards = [
      ["Events scored", fmt(SNAP.n_scored), "last " + SNAP.window_hours + " hours of data"],
      ["Likely to matter", fmt(SNAP.n_flagged), pct(SNAP.n_flagged / SNAP.n_scored, 1) + " of events, score ≥ " + SNAP.threshold.toFixed(2)],
      ["Test PR-AUC", m["PR-AUC"].toFixed(3), b ? '<span class="up">+' + (m["PR-AUC"] - b["PR-AUC"]).toFixed(3) + "</span> over counting publishers (" + b["PR-AUC"].toFixed(3) + ")" : ""],
      ["Data processed", (ds.uncompressed / 1e9).toFixed(1) + " GB", fmt(ds.files) + " GDELT files, 1 week"],
    ];
    $("#kpis").innerHTML = cards.map((c) => `<div class="glass kpi"><small>${c[0]}</small><b>${c[1]}</b><span>${c[2]}</span></div>`).join("");
  }

  function filters() {
    const types = Array.from(new Set(SNAP.events.map((e) => e.cameo_root))).sort();
    $("#fType").innerHTML = '<option value="">All types</option>' + types.map((t) => `<option value="${t}">${t} · ${CAMEO[t] || t}</option>`).join("");
    const cs = {}; SNAP.events.forEach((e) => (cs[e.geo_country] = (cs[e.geo_country] || 0) + 1));
    $("#fCountry").innerHTML = '<option value="">All countries</option>' + Object.keys(cs).sort((a, b) => cs[b] - cs[a]).map((c) => `<option value="${c}">${cname(c)} (${cs[c]})</option>`).join("");
    ["q", "fType", "fCountry", "minScore", "onlyFlag"].forEach((id) => $("#" + id).addEventListener("input", () => { S.shown = 40; $("#minScoreV").textContent = (+$("#minScore").value).toFixed(2); renderList(); }));
    $("#more").addEventListener("click", () => { S.shown += 40; renderList(); });
  }

  function filtered() {
    const q = $("#q").value.trim().toLowerCase(), t = $("#fType").value, c = $("#fCountry").value, ms = +$("#minScore").value, of = $("#onlyFlag").checked;
    return SNAP.events.filter((e) => (!t || e.cameo_root === t) && (!c || e.geo_country === c) && e.score >= ms && (!of || e.score >= SNAP.threshold) &&
      (!q || (headline(e.source_url) + " " + host(e.source_url) + " " + (e.geo_name || "")).toLowerCase().indexOf(q) !== -1));
  }

  function renderList() {
    const all = filtered(), rows = all.slice(0, S.shown);
    $("#list").innerHTML = rows.map((e) => {
      const i = SNAP.events.indexOf(e);
      return `<div class="glass row" data-i="${i}" tabindex="0">
        <div class="rk">${i + 1}</div>
        <div class="ring" style="--p:${e.score};--c:${col(e.score)}"><b>${Math.round(e.score * 100)}</b></div>
        <div><div class="hl">${esc(headline(e.source_url))}</div>
          <div class="meta"><span class="chip">${esc(host(e.source_url))}</span>${e.geo_name ? `<span class="chip">${esc(e.geo_name)}</span>` : ""}<span class="chip ac">${esc(CAMEO[e.cameo_root] || e.cameo_root)}</span><span class="chip">${e.src_1h} publisher${e.src_1h === 1 ? "" : "s"}</span>${e.score >= SNAP.threshold ? '<span class="chip ok">likely to matter</span>' : ""}</div></div>
        <div class="score"><div class="bar"><i style="width:${e.score * 100}%"></i><s style="left:${SNAP.threshold * 100}%"></s></div><div class="src">${when(e.t0)}</div></div>
      </div>`;
    }).join("") || '<div class="glass card"><p>No events match these filters.</p></div>';
    $("#count").textContent = "Showing " + rows.length + " of " + all.length;
    $("#more").style.display = rows.length < all.length ? "" : "none";
    $$(".row").forEach((r) => { const f = () => openDrawer(SNAP.events[+r.dataset.i]); r.addEventListener("click", f); r.addEventListener("keydown", (k) => { if (k.key === "Enter") f(); }); });
  }

  /* ---------- drawer ---------- */
  function openDrawer(e) {
    $("#dBody").innerHTML = `
      <span class="chip ${e.score >= SNAP.threshold ? "ok" : ""}">${e.score >= SNAP.threshold ? "Likely to matter" : "Below threshold"}</span>
      <h2>${esc(headline(e.source_url))}</h2>
      <div class="meta"><span class="chip">${esc(host(e.source_url))}</span>${e.geo_name ? `<span class="chip">${esc(e.geo_name)}</span>` : ""}<span class="chip">${when(e.t0)}</span></div>
      <div class="gauge" style="--p:${e.score};--c:${col(e.score)};width:150px;height:150px;margin:20px auto 6px"><div class="gin"><b style="font-size:34px">${e.score.toFixed(2)}</b><span style="font-size:11px;color:var(--mut)">score</span></div></div>
      <div class="dgrid">
        <div><small>Publishers, hour 1</small><b>${e.src_1h}</b></div><div><small>Mentions, hour 1</small><b>${e.m_1h}</b></div>
        <div><small>Event type</small><b style="font-size:14px">${esc(CAMEO[e.cameo_root] || e.cameo_root)}</b></div><div><small>Languages</small><b>${e.lang_1h}</b></div>
        <div><small>Average tone</small><b>${e.avg_tone}</b></div><div><small>Goldstein</small><b>${e.goldstein}</b></div>
      </div>
      <div class="dacts"><a class="btn pri" href="${esc(e.source_url)}" target="_blank" rel="noopener noreferrer">Open article</a><button class="btn" id="dTry">What if…? </button></div>`;
    $("#dTry").addEventListener("click", () => { closeDrawer(); loadIntoTry(e); go("try"); });
    $("#drawer").classList.add("on"); $("#scrim").classList.add("on"); $("#drawer").setAttribute("aria-hidden", "false");
  }
  function closeDrawer() { $("#drawer").classList.remove("on"); $("#scrim").classList.remove("on"); $("#drawer").setAttribute("aria-hidden", "true"); }
  $("#dClose").addEventListener("click", closeDrawer); $("#scrim").addEventListener("click", closeDrawer);
  document.addEventListener("keydown", (k) => { if (k.key === "Escape") closeDrawer(); });

  /* ---------- tabs ---------- */
  function tabs() { $$(".tabs button").forEach((b) => b.addEventListener("click", () => go(b.dataset.tab))); }
  function go(t) {
    $$(".tabs button").forEach((b) => b.classList.toggle("on", b.dataset.tab === t));
    $$(".view").forEach((v) => v.classList.toggle("on", v.id === "v-" + t));
    $("#kpis").style.display = t === "ranked" ? "" : "none";
    history.replaceState(null, "", "#" + t); window.scrollTo({ top: 0, behavior: "smooth" });
  }

  /* ---------- map ---------- */
  const vb = { x: 0, y: 0, w: 1000, h: 500 };
  function mapInit() {
    const svg = $("#map"), ns = "http://www.w3.org/2000/svg";
    const land = document.createElementNS(ns, "path"); land.setAttribute("d", WORLD.d); land.setAttribute("class", "land"); land.setAttribute("fill-rule", "evenodd"); svg.appendChild(land);
    const g = document.createElementNS(ns, "g"); svg.appendChild(g);
    SNAP.events.filter((e) => e.lat != null && e.lon != null).slice().reverse().forEach((e) => {
      const c = document.createElementNS(ns, "circle");
      c.setAttribute("cx", (e.lon + 180) / 360 * 1000); c.setAttribute("cy", (90 - e.lat) / 180 * 500);
      c.setAttribute("r", 2.6 + e.score * 4.4); c.setAttribute("fill", ramp((e.score - 0.75) / 0.25)); c.setAttribute("fill-opacity", ".72");
      c.addEventListener("mouseenter", (ev) => tip(ev, e)); c.addEventListener("mousemove", (ev) => tip(ev, e)); c.addEventListener("mouseleave", () => ($("#tip").style.opacity = 0));
      c.addEventListener("click", () => openDrawer(e)); g.appendChild(c);
    });
    const setVB = () => svg.setAttribute("viewBox", [vb.x, vb.y, vb.w, vb.h].join(" "));
    const zoom = (f, cx, cy) => { const nw = Math.min(1000, Math.max(80, vb.w * f)), nh = nw / 2; cx = cx == null ? vb.x + vb.w / 2 : cx; cy = cy == null ? vb.y + vb.h / 2 : cy; vb.x = Math.max(0, Math.min(1000 - nw, cx - (cx - vb.x) * (nw / vb.w))); vb.y = Math.max(0, Math.min(500 - nh, cy - (cy - vb.y) * (nh / vb.h))); vb.w = nw; vb.h = nh; setVB(); };
    const pt = (ev) => { const r = svg.getBoundingClientRect(); return [vb.x + (ev.clientX - r.left) / r.width * vb.w, vb.y + (ev.clientY - r.top) / r.height * vb.h]; };
    svg.addEventListener("wheel", (ev) => { ev.preventDefault(); const p = pt(ev); zoom(ev.deltaY < 0 ? 0.8 : 1.25, p[0], p[1]); }, { passive: false });
    let drag = null; svg.addEventListener("pointerdown", (ev) => { drag = { x: ev.clientX, y: ev.clientY, vx: vb.x, vy: vb.y }; });
    window.addEventListener("pointerup", () => (drag = null));
    window.addEventListener("pointermove", (ev) => { if (!drag) return; const r = svg.getBoundingClientRect(); vb.x = Math.max(0, Math.min(1000 - vb.w, drag.vx - (ev.clientX - drag.x) / r.width * vb.w)); vb.y = Math.max(0, Math.min(500 - vb.h, drag.vy - (ev.clientY - drag.y) / r.height * vb.h)); setVB(); });
    $("#zin").onclick = () => zoom(0.7); $("#zout").onclick = () => zoom(1.4); $("#zreset").onclick = () => { vb.x = 0; vb.y = 0; vb.w = 1000; vb.h = 500; setVB(); };
  }
  function ramp(p) { const a = [165, 180, 252], b = [124, 58, 237], t = Math.min(1, Math.max(0, p)); return "rgb(" + a.map((v, i) => Math.round(v + (b[i] - v) * t)).join(",") + ")"; }
  function tip(ev, e) {
    const t = $("#tip"), w = $(".mapwrap").getBoundingClientRect();
    t.innerHTML = `<b>${esc(headline(e.source_url)).slice(0, 80)}</b>${esc(e.geo_name || "")} · score ${e.score.toFixed(2)}`;
    t.style.left = ev.clientX - w.left + "px"; t.style.top = ev.clientY - w.top + "px"; t.style.opacity = 1;
  }

  /* ---------- trends ---------- */
  function trends() {
    const H = SNAP.hourly.slice(1, -1), W = 1000, Ht = 300, pl = 44, pr = 44, pt = 14, pb = 36, iw = W - pl - pr, ih = Ht - pt - pb;
    const mx = Math.max.apply(null, H.map((h) => h.imp)) * 1.15, bw = iw / H.length;
    let s = `<svg viewBox="0 0 ${W} ${Ht}" role="img" aria-label="Flagged events per hour"><defs><linearGradient id="gb" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#8b5cf6"/><stop offset="1" stop-color="#6366f1" stop-opacity=".55"/></linearGradient></defs>`;
    for (let i = 0; i <= 4; i++) { const y = pt + ih - ih * i / 4; s += `<line x1="${pl}" x2="${W - pr}" y1="${y}" y2="${y}" stroke="rgba(120,130,190,.18)"/><text x="${pl - 8}" y="${y + 4}" text-anchor="end" font-size="11" fill="#8b93b1">${Math.round(mx * i / 4)}</text>`; }
    H.forEach((h, i) => { const bh = h.imp / mx * ih; s += `<rect x="${pl + i * bw + bw * .18}" y="${pt + ih - bh}" width="${bw * .64}" height="${bh}" rx="6" fill="url(#gb)"><title>${h.h}: ${h.imp} flagged of ${h.n}</title></rect>`;
      if (i % 3 === 0) s += `<text x="${pl + i * bw + bw / 2}" y="${Ht - 12}" text-anchor="middle" font-size="11" fill="#8b93b1">${h.h.slice(5, 10).replace("-", "/")} ${h.h.slice(11, 13)}h</text>`; });
    const mm = Math.max.apply(null, H.map((h) => h.mean)) * 1.15;
    const pts = H.map((h, i) => [pl + i * bw + bw / 2, pt + ih - h.mean / mm * ih]);
    s += `<path d="${pts.map((p, i) => (i ? "L" : "M") + p[0].toFixed(1) + "," + p[1].toFixed(1)).join("")}" fill="none" stroke="#22b8cf" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>` + pts.map((p) => `<circle cx="${p[0]}" cy="${p[1]}" r="3.5" fill="#fff" stroke="#22b8cf" stroke-width="2"/>`).join("");
    for (let i = 0; i <= 4; i++) s += `<text x="${W - pr + 8}" y="${pt + ih - ih * i / 4 + 4}" font-size="11" fill="#22b8cf">${(mm * i / 4).toFixed(2)}</text>`;
    $("#cHourly").innerHTML = s + "</svg>";
    bars($("#cCountry"), Object.entries(SNAP.countries).map(([k, v]) => ({ l: cname(k), v: v })));
    bars($("#cType"), Object.entries(SNAP.types).map(([k, v]) => ({ l: CAMEO[k] || k, v: v })));
  }

  /* ---------- model ---------- */
  function model() {
    const M = SNAP.metrics.slice().sort((a, b) => a["PR-AUC"] - b["PR-AUC"]);
    const mx = 0.7, el = $("#cModels");
    el.innerHTML = M.concat([]).sort((a, b) => b["PR-AUC"] - a["PR-AUC"]).map((m) => {
      const base = m.model === "baseline_src_1h", champ = m.model === SNAP.champion;
      const lab = base ? "Count publishers (baseline)" : m.label;
      return `<div class="hb" style="grid-template-columns:190px 1fr 120px"><span title="${esc(lab)}">${esc(lab)}</span><div class="bar" style="height:14px;overflow:visible"><i style="width:${m["PR-AUC"] / mx * 100}%;${base ? "background:#cbd5e1" : champ ? "" : "background:linear-gradient(90deg,#c7d2fe,#a5b4fc)"}"></i>${m["PR-AUC lo"] ? `<s style="left:${m["PR-AUC lo"] / mx * 100}%;width:${(m["PR-AUC hi"] - m["PR-AUC lo"]) / mx * 100}%;top:5px;bottom:5px;background:rgba(27,33,64,.5)"></s>` : ""}</div><em>${m["PR-AUC"].toFixed(3)}${champ ? " ★" : ""} <small style="color:var(--faint);font-weight:500">F1 ${m.F1.toFixed(2)}</small></em></div>`;
    }).join("");
    bars($("#cImp"), SNAP.importance.map((r) => ({ l: r[0].replace(/_ix$/, "").replace(/_/g, " "), v: r[1], t: (r[1] * 100).toFixed(1) + "%" })));
    const B = SNAP.buckets;
    $("#cBuckets").innerHTML = B.map((b) => `<div class="hb" style="grid-template-columns:78px 1fr 92px"><span>${b.bucket} pub.</span><div class="bar"><i style="width:${b.share_of_positives * 100 / 0.4 }%;${b.recall < 0.2 ? "background:linear-gradient(90deg,#fbbf24,#f59e0b)" : ""}"></i></div><em>${pct(b.share_of_positives)} <small style="color:var(--faint);font-weight:500">r ${pct(b.recall)}</small></em></div>`).join("") +
      `<p class="hint" style="margin-top:10px">Bar: share of important events. r: recall. ${pct(B[0].share_of_positives)} of important events have a single publisher at hour one, and we catch only ${pct(B[0].recall)} of those.</p>`;
    const p = SNAP.parity, d = SNAP.vs_baseline.diff;
    $("#proof").innerHTML = `<div><b>+${d.ap.mean.toFixed(3)}</b><span>PR-AUC over baseline (CI ${d.ap.lo.toFixed(3)} to ${d.ap.hi.toFixed(3)})</span></div><div><b>${fmt(p.compared)}</b><span>streamed events compared with batch</span></div><div><b>${p.max_abs_score_diff.toFixed(1)}</b><span>max score difference, Kafka stream vs batch</span></div>`;
  }

  /* ---------- try ---------- */
  const PRESETS = {
    "Local protest": { src: 2, m: 3, lang: 1, tone: -3, gold: -4, prior: 0.05, type: "14", country: "OTHER" },
    "Borderline": { src: 3, m: 5, lang: 1, tone: -3, gold: -4, prior: 0.03, type: "14", country: "OTHER" },
    "Wire-covered summit": { src: 22, m: 70, lang: 5, tone: 1, gold: 4, prior: 0.35, type: "05", country: "US" },
    "Single-source rumor": { src: 1, m: 1, lang: 1, tone: -6, gold: -5, prior: 0.03, type: "01", country: "OTHER" },
    "Conflict breaking": { src: 9, m: 28, lang: 3, tone: -7, gold: -8, prior: 0.2, type: "19", country: "IS" },
  };
  function tryInit() {
    $("#i_type").innerHTML = Object.keys(CAMEO).map((k) => `<option value="${k}">${k} · ${CAMEO[k]}</option>`).join("");
    const cs = MODEL.vocab.geo_country.filter((c) => c !== "NA");
    $("#i_country").innerHTML = cs.map((c) => `<option value="${c}">${cname(c)}</option>`).join("") + '<option value="OTHER">Other</option>';
    $("#thrV").textContent = SNAP.threshold.toFixed(2);
    $("#presets").innerHTML = Object.keys(PRESETS).map((k) => `<button data-p="${k}">${k}</button>`).join("");
    $$("#presets button").forEach((b) => b.addEventListener("click", () => setForm(PRESETS[b.dataset.p])));
    ["src", "m", "lang", "tone", "gold", "prior", "type", "country"].forEach((k) => $("#i_" + k).addEventListener("input", tryRender));
    setForm(PRESETS["Local protest"]);
  }
  function setForm(p) { Object.keys(p).forEach((k) => { $("#i_" + k).value = p[k]; }); tryRender(); }
  function loadIntoTry(e) {
    const prior = 0.1; setForm({ src: Math.min(40, e.src_1h), m: Math.min(120, e.m_1h), lang: Math.min(8, Math.max(1, e.lang_1h)), tone: Math.max(-10, Math.min(10, Math.round(e.avg_tone * 2) / 2)), gold: Math.max(-10, Math.min(10, Math.round(e.goldstein * 2) / 2)), prior: prior, type: e.cameo_root, country: MODEL.vocab.geo_country.indexOf(e.geo_country) !== -1 ? e.geo_country : "OTHER" });
  }
  function rowFrom(v) {
    const m = Math.max(v.m, v.src), lang = v.lang, q = QUAD(v.type);
    return { m_1h: m, m_15m: Math.max(1, Math.round(m * 0.4)), src_1h: v.src, lang_1h: lang, nonen_1h: Math.min(m, (lang - 1) * 2), art_1h: m, tone_mean_1h: v.tone, tone_std_1h: v.src > 1 ? 2 : 0, conf_mean_1h: 80, doclen_mean_1h: 2000, goldstein: v.gold, avg_tone: v.tone, quad_class: q, is_root_event: 1, geo_type: 4, has_actor1_country: 1, has_actor2_country: 0, has_geo: 1, num_mentions_export: m, num_sources_export: v.src, n_themes_1h: 12, pub_prior_mean: v.prior, pub_prior_max: Math.min(1, v.prior * 1.5), pub_known_frac: 1, cameo_root: v.type, geo_country: v.country, actor1_country: v.country === "US" ? "USA" : "NA" };
  }
  function vals() { return { src: +$("#i_src").value, m: +$("#i_m").value, lang: +$("#i_lang").value, tone: +$("#i_tone").value, gold: +$("#i_gold").value, prior: +$("#i_prior").value, type: $("#i_type").value, country: $("#i_country").value }; }
  function tryRender() {
    const v = vals();
    $("#o_src").textContent = v.src; $("#o_m").textContent = v.m; $("#o_lang").textContent = v.lang; $("#o_tone").textContent = v.tone.toFixed(1); $("#o_gold").textContent = v.gold.toFixed(1); $("#o_prior").textContent = v.prior.toFixed(2);
    const p = GBT.score(MODEL, rowFrom(v)), g = $("#gauge");
    g.style.setProperty("--p", p); g.style.setProperty("--c", col(p));
    $("#gScore").textContent = p.toFixed(2);
    const ok = p >= SNAP.threshold; $("#gVerdict").textContent = ok ? "Likely to matter" : "Probably stays small"; $("#gVerdict").style.color = ok ? "#047857" : "#64748b";
    sweep(v);
  }
  function sweep(v) {
    const W = 600, H = 220, pl = 36, pr = 12, pt = 12, pb = 28, iw = W - pl - pr, ih = H - pt - pb, pts = [];
    for (let s = 1; s <= 25; s++) pts.push([s, GBT.score(MODEL, rowFrom(Object.assign({}, v, { src: s, m: Math.max(v.m, s) })))]);
    const X = (s) => pl + (s - 1) / 24 * iw, Y = (p) => pt + ih - p * ih, d = pts.map((q, i) => (i ? "L" : "M") + X(q[0]).toFixed(1) + "," + Y(q[1]).toFixed(1)).join("");
    let o = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Score versus publishers"><defs><linearGradient id="ga" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#8b5cf6" stop-opacity=".28"/><stop offset="1" stop-color="#8b5cf6" stop-opacity="0"/></linearGradient></defs>`;
    [0, .25, .5, .75, 1].forEach((t) => (o += `<line x1="${pl}" x2="${W - pr}" y1="${Y(t)}" y2="${Y(t)}" stroke="rgba(120,130,190,.18)"/><text x="${pl - 6}" y="${Y(t) + 4}" text-anchor="end" font-size="10.5" fill="#8b93b1">${t}</text>`));
    o += `<line x1="${pl}" x2="${W - pr}" y1="${Y(SNAP.threshold)}" y2="${Y(SNAP.threshold)}" stroke="#10b981" stroke-dasharray="5 4"/><text x="${W - pr}" y="${Y(SNAP.threshold) - 5}" text-anchor="end" font-size="10.5" fill="#059669">threshold</text>`;
    o += `<path d="${d}L${X(25)},${Y(0)}L${X(1)},${Y(0)}Z" fill="url(#ga)"/><path d="${d}" fill="none" stroke="#6d5ef0" stroke-width="3" stroke-linejoin="round"/>`;
    [1, 5, 10, 15, 20, 25].forEach((s) => (o += `<text x="${X(s)}" y="${H - 8}" text-anchor="middle" font-size="10.5" fill="#8b93b1">${s}</text>`));
    const cur = GBT.score(MODEL, rowFrom(v));
    o += `<circle cx="${X(v.src)}" cy="${Y(cur)}" r="6" fill="#fff" stroke="#6d5ef0" stroke-width="3"/></svg>`;
    $("#cSweep").innerHTML = o;
  }
})();
