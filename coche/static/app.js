/* Coche web app - vanilla JS, no build step.
   State lives in S (filled by /api/coche/bootstrap); every view is a function that
   returns HTML; one delegated click handler dispatches [data-a] actions. */
"use strict";
(() => {
const BOOT = window.COCHE_BOOT || { base: "" };
const BASE = BOOT.base || "";
const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const sleep = ms => new Promise(r => setTimeout(r, ms));
const pad = n => String(n).padStart(2, "0");
const fold = s => String(s || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
const cap = s => s ? s[0].toUpperCase() + s.slice(1) : s;

/* ------------------------------------------------------------------ i18n */
const FR = window.COCHE_FR || {};
let LANG = "en";
const t = (s, ...a) => { let x = (LANG === "fr" && FR[s]) || s; a.forEach((v, i) => { x = x.split("{" + i + "}").join(v); }); return x; };
const plural = (n, one, many) => t(n === 1 ? one : many, n);

/* ------------------------------------------------------------------ icons */
const IC = {
  check: '<path d="M20 6 9 17l-5-5"/>', plus: '<path d="M12 5v14M5 12h14"/>', x: '<path d="M18 6 6 18M6 6l12 12"/>',
  search: '<circle cx="11" cy="11" r="7"/><path d="m21 21-4.3-4.3"/>', menu: '<path d="M4 6h16M4 12h16M4 18h16"/>',
  more: '<circle cx="5" cy="12" r="1.6" class="f"/><circle cx="12" cy="12" r="1.6"/><circle cx="19" cy="12" r="1.6"/>',
  inbox: '<path d="M22 12h-6l-2 3h-4l-2-3H2"/><path d="M5.45 5.11 2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11z"/>',
  cal: '<rect x="3" y="4" width="18" height="18" rx="2"/><path d="M16 2v4M8 2v4M3 10h18"/>',
  up: '<rect x="3" y="4" width="18" height="18" rx="2"/><path d="M16 2v4M8 2v4M3 10h18M8 14h.01M12 14h.01M16 14h.01M8 18h.01M12 18h.01"/>',
  grid: '<rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/>',
  flag: '<path d="M5 21V4h12l-2.5 4.5L17 13H5"/>', tag: '<path d="M20.6 13.4 13.4 20.6a2 2 0 0 1-2.8 0L3 13V3h10l7.6 7.6a2 2 0 0 1 0 2.8z"/><circle cx="7.5" cy="7.5" r="1.5"/>',
  bell: '<path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9"/><path d="M10.3 21a1.94 1.94 0 0 0 3.4 0"/>',
  repeat: '<path d="m17 2 4 4-4 4"/><path d="M3 11v-1a4 4 0 0 1 4-4h14"/><path d="m7 22-4-4 4-4"/><path d="M21 13v1a4 4 0 0 1-4 4H3"/>',
  clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>', comment: '<path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>',
  trash: '<path d="M3 6h18M8 6V4h8v2M19 6l-1 14H6L5 6M10 11v5M14 11v5"/>', down: '<path d="m6 9 6 6 6-6"/>', right: '<path d="m9 6 6 6-6 6"/>',
  left: '<path d="m15 6-6 6 6 6"/>', sliders: '<path d="M4 21v-7M4 10V3M12 21v-9M12 8V3M20 21v-5M20 12V3M1 14h6M9 8h6M17 16h6"/>',
  hash: '<path d="M4 9h16M4 15h16M10 3 8 21M16 3l-2 18"/>', star: '<path d="m12 2 3.1 6.3 6.9 1-5 4.9 1.2 6.8L12 17.8 5.8 21l1.2-6.8-5-4.9 6.9-1z"/>',
  archive: '<rect x="2" y="3" width="20" height="5" rx="1"/><path d="M4 8v11a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8M10 12h4"/>',
  sub: '<path d="M6 3v12"/><circle cx="18" cy="6" r="3"/><circle cx="6" cy="18" r="3"/><path d="M18 9a9 9 0 0 1-9 9"/>',
  board: '<rect x="3" y="3" width="18" height="18" rx="2"/><path d="M9 3v18M15 3v18"/>', list: '<path d="M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01"/>',
  target: '<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="5"/><circle cx="12" cy="12" r="1"/>',
  sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>',
  sofa: '<path d="M17 8h1a4 4 0 1 1 0 8h-1M3 8h14v9a4 4 0 0 1-4 4H7a4 4 0 0 1-4-4z"/>', arrow: '<path d="M5 12h14M13 6l6 6-6 6"/>',
  ban: '<circle cx="12" cy="12" r="9"/><path d="m5.6 5.6 12.8 12.8"/>', done: '<circle cx="12" cy="12" r="9"/><path d="m8 12 3 3 5-6"/>',
  logout: '<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4M16 17l5-5-5-5M21 12H9"/>', copy: '<rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>',
  chart: '<path d="M3 3v18h18M7 16v-5M12 16V8M17 16v-3"/>', edit: '<path d="M17 3a2.8 2.8 0 0 1 4 4L7.5 20.5 2 22l1.5-5.5z"/>',
  drag: '<circle cx="9" cy="6" r="1.4"/><circle cx="15" cy="6" r="1.4"/><circle cx="9" cy="12" r="1.4"/><circle cx="15" cy="12" r="1.4"/><circle cx="9" cy="18" r="1.4"/><circle cx="15" cy="18" r="1.4"/>',
  sidebar: '<rect x="3" y="3" width="18" height="18" rx="2"/><path d="M9 3v18"/>', key: '<circle cx="7.5" cy="15.5" r="5.5"/><path d="m21 2-9.6 9.6M15.5 7.5l3 3L22 7l-3-3"/>',
  dl: '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M7 10l5 5 5-5M12 15V3"/>', ul: '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M17 8l-5-5-5 5M12 3v12"/>',
  flame: '<path d="M8.5 14.5A2.5 2.5 0 0 0 11 12c0-1.38-.5-2-1-3-1.07-2.14-.22-4.05 2-6 .5 2.5 2 4.9 4 6.5 2 1.6 3 3.5 3 5.5a7 7 0 1 1-14 0c0-1.15.43-2.29 1-3a2.5 2.5 0 0 0 2.5 2.5z"/>',
  globe: '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3a14 14 0 0 1 0 18M12 3a14 14 0 0 0 0 18"/>', zap: '<path d="M13 2 3 14h9l-1 8 10-12h-9z"/>',
};
const ic = (n, cls = "") => `<svg class="i ${cls}" viewBox="0 0 24 24" aria-hidden="true">${n === "more" ? IC.more.replace(/<circle/g, '<circle fill="currentColor" stroke="none"') : n === "drag" ? IC.drag.replace(/<circle/g, '<circle fill="currentColor" stroke="none"') : IC[n] || ""}</svg>`;
const todayIcon = d => `<svg class="i" viewBox="0 0 24 24" aria-hidden="true">${IC.cal}<text x="12" y="19" text-anchor="middle" font-size="8.5" font-weight="700" fill="currentColor" stroke="none" font-family="system-ui">${d}</text></svg>`;
const COLORS = { berry_red: "#b8255f", red: "#db4035", orange: "#ff9933", yellow: "#fad000", olive_green: "#afb83b", lime_green: "#7ecc49", green: "#299438", mint_green: "#6accbc", teal: "#158fad", sky_blue: "#14aaf5", light_blue: "#96c3eb", blue: "#4073ff", grape: "#884dff", violet: "#af38eb", lavender: "#eb96eb", magenta: "#e05194", salmon: "#ff8d85", charcoal: "#808080", grey: "#b8b8b8", taupe: "#ccac93" };
const col = c => COLORS[c] || COLORS.charcoal;
const PRIO = { 4: "p1", 3: "p2", 2: "p3", 1: "p4" };

/* ------------------------------------------------------------------ state */
const S = { projects: [], archived_projects: [], sections: [], labels: [], filters: [], tasks: [], reminders: [], settings: {}, stats: {}, app: {} };
let byId = new Map(), kids = new Map(), projById = new Map(), secById = new Map();
const byOrder = (a, b) => (a.child_order - b.child_order) || String(a.added_at).localeCompare(String(b.added_at));
function reindex() {
  byId = new Map(S.tasks.map(x => [x.id, x]));
  kids = new Map();
  for (const x of S.tasks) if (x.parent_id && byId.has(x.parent_id)) { if (!kids.has(x.parent_id)) kids.set(x.parent_id, []); kids.get(x.parent_id).push(x); }
  for (const v of kids.values()) v.sort(byOrder);
  projById = new Map([...S.projects, ...S.archived_projects].map(p => [p.id, p]));
  secById = new Map(S.sections.map(s => [s.id, s]));
}
function put(x) {
  const i = S.tasks.findIndex(y => y.id === x.id);
  if (x.checked || x.is_deleted) { if (i >= 0) S.tasks.splice(i, 1); }
  else if (i >= 0) S.tasks[i] = x; else S.tasks.push(x);
  reindex();
}
function dropTree(id) {
  const gone = new Set([id]); let grew = true;
  while (grew) { grew = false; for (const x of S.tasks) if (x.parent_id && gone.has(x.parent_id) && !gone.has(x.id)) { gone.add(x.id); grew = true; } }
  S.tasks = S.tasks.filter(x => !gone.has(x.id)); reindex(); return gone;
}
const inbox = () => S.projects.find(p => p.is_inbox_project) || S.projects[0] || {};
const projName = p => p && p.is_inbox_project ? t("Inbox") : (p ? p.name : "");

/* ------------------------------------------------------------------ api */
let offline = false;
const API_TIMEOUT = 10000;   // no answer in 10 s = offline (a weak network would otherwise hang the action)
/* rid: X-Request-Id, so the same action sent again (offline queue) runs once on the server. Errors carry
   .offline (no answer) or .status (HTTP error). An answer served from the service worker's cache = offline. */
async function api(method, path, body, rid) {
  const opt = { method, headers: {}, credentials: "same-origin" };
  if (body !== undefined) { opt.headers["Content-Type"] = "application/json"; opt.body = JSON.stringify(body); }
  if (rid) opt.headers["X-Request-Id"] = rid;
  const ctl = new AbortController(), timer = setTimeout(() => ctl.abort(), API_TIMEOUT); opt.signal = ctl.signal;
  let r;
  try { r = await fetch(BASE + path, opt); }
  catch (e) { setOffline(true); throw Object.assign(new Error(t("Offline: only completing and adding tasks work for now")), { offline: true }); }
  finally { clearTimeout(timer); }
  const cached = !!r.headers.get("X-Cached-At");
  setOffline(cached);
  if (r.status === 401 && BOOT.protected) { location.href = BASE + "/login"; throw new Error("unauthorized"); }
  if (!cached && OUTBOX && OUTBOX.list().length && !SYNCING) setTimeout(syncOutbox, 0);
  if (r.status === 204) return null;
  const data = await r.json().catch(() => null);
  if (!r.ok) throw Object.assign(new Error((data && data.error) || ("HTTP " + r.status)), { status: r.status });
  return data;
}
function setOffline(v) { offline = v; banner(); }
function banner() {
  const b = $("#c-offline"); if (!b) return;
  const n = OUTBOX ? OUTBOX.list().length : 0;
  b.hidden = !offline && !n;
  b.textContent = (offline ? t("Offline: showing your last synced tasks") : t("Syncing…")) + (n ? " · " + t("{0} waiting to sync", n) : "");
}

/* ------------------------------------------------------------------ offline queue (outbox.js) */
const OUTBOX = window.CocheOutbox ? window.CocheOutbox.create(localStorage) : null;
let SYNCING = false;
function overlay() { if (OUTBOX) { for (const op of OUTBOX.list()) CocheOutbox.applyLocal(S, op); reindex(); } }
function rebuild() {   // server state from the local copy + what is still queued
  try { const c = JSON.parse(localStorage.getItem("coche-cache") || "null"); if (c) Object.assign(S, c); } catch (e) { /* bad cache */ }
  reindex(); overlay(); render();
}
async function syncOutbox() {
  if (!OUTBOX || SYNCING || !OUTBOX.list().length) return;
  SYNCING = true; banner();
  let res;
  try { res = await CocheOutbox.replay(OUTBOX, (m, p, b, rid) => api(m, p, b, rid)); }
  finally { SYNCING = false; }
  banner();
  if (res.done || res.failed) await load(true);
  if (res.failed) toast(t("{0} offline changes could not be saved", res.failed));
}
function queueOffline(op) { const o = OUTBOX.push(op); CocheOutbox.applyLocal(S, o); reindex(); banner(); return o; }
const run = fn => async (...a) => { try { return await fn(...a); } catch (e) { toast(e.message || String(e)); } };

async function load(quiet) {
  try {
    const b = await api("GET", "/api/coche/bootstrap");
    Object.assign(S, b); reindex(); applySettings();
    try { localStorage.setItem("coche-cache", JSON.stringify(b)); } catch (e) { /* quota */ }
    overlay(); banner();   // the banner text follows the language just read from the settings
    render(quiet);
  } catch (e) { if (!quiet) toast(e.message); }
}

/* ------------------------------------------------------------------ dates */
const D = s => { const [y, m, d] = String(s).slice(0, 10).split("-").map(Number); return new Date(y, m - 1, d); };
const iso = d => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
const addDays = (d, n) => { const x = new Date(d); x.setDate(x.getDate() + n); return x; };
const todayD = () => { const n = new Date(); return new Date(n.getFullYear(), n.getMonth(), n.getDate()); };
const todayS = () => iso(todayD());
const nowHM = () => { const n = new Date(); return pad(n.getHours()) + ":" + pad(n.getMinutes()); };
const locale = () => LANG === "fr" ? "fr-FR" : (S.settings.date_order === "MDY" ? "en-US" : "en-GB");
const fmt = (d, o) => new Intl.DateTimeFormat(locale(), o).format(d);
const wdShort = d => fmt(d, { weekday: "short" }).replace(/\.$/, "") + (LANG === "fr" ? "." : "");
const wdLong = d => fmt(d, { weekday: "long" });
const dm = d => { const a = pad(d.getDate()), b = pad(d.getMonth() + 1); return S.settings.date_order === "MDY" ? `${b}/${a}` : `${a}/${b}`; };
const dmy = d => dm(d) + (d.getFullYear() !== todayD().getFullYear() ? "/" + String(d.getFullYear()).slice(2) : "");
function hm(s) {
  if (!s) return "";
  if (S.settings.time_format !== "12h") return s;
  let [h, m] = s.split(":").map(Number); const ap = h >= 12 ? "pm" : "am"; h = h % 12 || 12;
  return m ? `${h}:${pad(m)}${ap}` : `${h}${ap}`;
}
const dayDiff = ds => Math.round((D(ds) - todayD()) / 864e5);
function dayLabel(ds, long) {
  const n = dayDiff(ds), d = D(ds);
  if (n === 0) return t("Today");
  if (n === 1) return t("Tomorrow");
  if (n === -1) return t("Yesterday");
  if (n > 1 && n < 7) return long ? cap(wdLong(d)) : cap(wdLong(d));
  return `${cap(wdShort(d))} ${dmy(d)}`;
}
const dueDay = x => x.due ? x.due.date.slice(0, 10) : null;
const dueTime = x => x.due && x.due.date.length > 10 ? x.due.date.slice(11, 16) : null;
function isOverdue(x) {
  const d = dueDay(x); if (!d) return false;
  const n = dayDiff(d); return n < 0 || (n === 0 && dueTime(x) && dueTime(x) < nowHM());
}
function dueInfo(x, onlyTime) {
  const d = dueDay(x); if (!d) return null;
  const n = dayDiff(d), tm = dueTime(x);
  const cls = isOverdue(x) ? "due-over" : n === 0 ? "due-today" : n === 1 ? "due-tom" : n < 7 ? "due-week" : "";
  const text = onlyTime ? hm(tm) : dayLabel(d) + (tm ? " " + hm(tm) : "");
  return { text, cls };
}

/* ------------------------------------------------------------------ routing */
let R = { view: "today" };
function parseRoute() {
  const p = location.pathname.slice(BASE.length).replace(/^\/+/, "").split("/");
  const q = new URLSearchParams(location.search);
  const v = p[0] || "today";
  if (v === "task" && p[1]) { setTimeout(() => openDetail(p[1]), 0); return { view: "today" }; }
  if (["project", "label", "filter"].includes(v)) return { view: v, id: decodeURIComponent(p[1] || "") };
  if (["today", "inbox", "upcoming", "search", "completed", "settings", "labels"].includes(v)) return { view: v, q: q.get("q") || "" };
  return { view: "today" };
}
function go(path, replace) {
  const url = BASE + path;
  if (replace) history.replaceState({}, "", url); else history.pushState({}, "", url);
  R = parseRoute(); closeNav(); render(); $("#view").scrollTop = 0;
}
const href = p => BASE + p;
addEventListener("popstate", () => { if (!location.hash.startsWith("#task=")) closeDetail(true); R = parseRoute(); render(); });
addEventListener("hashchange", () => { if (!location.hash.startsWith("#task=")) closeDetail(true); });

/* ------------------------------------------------------------------ settings & theme */
function applySettings() {
  const s = S.settings || {};
  LANG = !s.lang || s.lang === "auto" ? ((navigator.language || "en").toLowerCase().startsWith("fr") ? "fr" : "en") : s.lang.slice(0, 2);
  document.documentElement.lang = LANG;
  const mq = matchMedia("(prefers-color-scheme: dark)");
  const theme = s.theme === "auto" || !s.theme ? (mq.matches ? "dark" : "light") : s.theme;
  if (!document.documentElement.hasAttribute("data-theme-lock")) document.documentElement.dataset.theme = theme;
  if (s.accent && !document.documentElement.hasAttribute("data-accent-lock")) document.documentElement.style.setProperty("--accent", s.accent);
  const m = $('meta[name="theme-color"]'); if (m) m.content = getComputedStyle(document.body).getPropertyValue("--bg").trim() || "#1e1e1e";
}
matchMedia("(prefers-color-scheme: dark)").addEventListener?.("change", applySettings);

/* ------------------------------------------------------------------ markdown-lite */
function md(s) {
  let h = esc(s);
  h = h.replace(/`([^`]+)`/g, "<code>$1</code>")
    .replace(/\*\*([^*]+)\*\*/g, "<b>$1</b>")
    .replace(/(^|[^*\w])\*([^*\s][^*]*)\*/g, "$1<i>$2</i>")
    .replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g, '<a href="$2" target="_blank" rel="noopener" data-ext>$1</a>')
    .replace(/(^|\s)(https?:\/\/[^\s<]+)/g, '$1<a href="$2" target="_blank" rel="noopener" data-ext>$2</a>');
  return h;
}

/* ------------------------------------------------------------------ task rows */
function countDeep(id) { let n = 0; for (const k of kids.get(id) || []) n += 1 + countDeep(k.id); return n; }
const remOf = id => S.reminders.filter(r => r.item_id === id && r.minute_offset !== -1);
const autoOn = x => S.settings.auto_reminder !== null && S.settings.auto_reminder !== undefined && !!dueTime(x)
  && !S.reminders.some(r => r.item_id === x.id && (r.minute_offset === -1 || (r.minute_offset === S.settings.auto_reminder && !r.at && !r.time)));
const remCount = x => remOf(x.id).length + (autoOn(x) ? 1 : 0);
function taskHTML(x, ctx = {}) {
  const sub = ctx.nest ? (kids.get(x.id) || []) : [];
  const nsub = countDeep(x.id);
  const p = PRIO[x.priority];
  const di = ctx.done ? null : dueInfo(x, ctx.onlyTime);
  const proj = projById.get(x.project_id), sec = secById.get(x.section_id);
  const meta = [];
  if (x.pending) meta.push(`<span class="pending" title="${esc(t("Waiting to sync"))}">⏳ ${esc(t("Waiting to sync"))}</span>`);
  if (di && di.text) meta.push(`<span class="${di.cls}">${ic(x.due.is_recurring ? "repeat" : "cal", "xs")}${esc(di.text)}</span>`);
  else if (x.due && x.due.is_recurring) meta.push(`<span>${ic("repeat", "xs")}</span>`);
  if (x.deadline) { const n = dayDiff(x.deadline.date); meta.push(`<span class="${n < 0 ? "due-over" : n <= 2 ? "due-tom" : ""}" title="${esc(t("Deadline"))}">${ic("target", "xs")}${esc(dayLabel(x.deadline.date))}</span>`); }
  if (x.duration) meta.push(`<span>${ic("clock", "xs")}${fmtDur(x.duration.amount)}</span>`);
  if (!ctx.nest && nsub) meta.push(`<span>${ic("sub", "xs")}${nsub}</span>`);
  else if (ctx.nest && nsub && closedTwisty(x)) meta.push(`<span>${ic("sub", "xs")}${nsub}</span>`);
  if (x.note_count) meta.push(`<span>${ic("comment", "xs")}${x.note_count}</span>`);
  const nrem = remCount(x); if (nrem) meta.push(`<span title="${esc(plural(nrem, "{0} reminder", "{0} reminders"))}">${ic("bell", "xs")}${nrem > 1 ? nrem : ""}</span>`);
  for (const l of x.labels) { const L = S.labels.find(y => y.name === l); meta.push(`<span class="lab" style="color:${L && L.color !== "charcoal" ? col(L.color) : ""}">${ic("tag", "xs")}${esc(l)}</span>`); }
  if (ctx.showProject && proj) meta.push(`<span class="proj">${esc(projName(proj))}${sec ? " / " + esc(sec.name) : ""} <i class="dot" style="background:${col(proj.color)}"></i></span>`);
  const desc = x.description ? `<div class="desc">${esc(x.description.split("\n")[0])}</div>` : "";
  const closed = closedTwisty(x);
  const subs = sub.length && !closed ? `<ul class="subs list" data-drop="sub" data-parent="${x.id}" data-project="${x.project_id}">${sub.map(k => taskHTML(k, { ...ctx, showProject: false })).join("")}</ul>` : "";
  return `<li class="task${ctx.done ? " done-row" : ""}${SEL === x.id ? " sel" : ""}" data-id="${x.id}">
  <div class="row" data-a="open">
    ${ctx.drag ? `<span class="handle" title="${esc(t("Drag to reorder"))}">${ic("drag", "s")}</span>` : ""}
    ${ctx.nest && (kids.get(x.id) || []).length ? `<button class="twisty${closed ? " closed" : ""}" data-a="twisty" aria-label="${esc(t("Subtasks"))}">${ic("down", "xs")}</button>` : ""}
    <button class="check ${p}${ctx.done ? " done" : ""}${x.due && x.due.is_recurring ? " rec" : ""}" data-a="${ctx.done ? "uncheck" : "check"}" aria-label="${esc(t(ctx.done ? "Uncomplete" : "Complete"))}">${ic("check")}</button>
    <div class="body"><div class="content">${md(x.content)}</div>${desc}${meta.length ? `<div class="meta">${meta.join("")}</div>` : ""}</div>
    ${ctx.done ? "" : `<span class="row-actions">
      <button class="ib" data-a="row-date" title="${esc(t("Schedule"))}">${ic("cal", "s")}</button>
      <button class="ib" data-a="row-more" title="${esc(t("More"))}">${ic("more", "s")}</button></span>`}
  </div>${subs}</li>`;
}
const collapsed = new Set(JSON.parse(localStorage.getItem("coche-collapsed") || "[]"));
const closedTwisty = x => x.is_collapsed || collapsed.has(x.id);
const fmtDur = m => m >= 60 ? `${Math.floor(m / 60)}h${m % 60 ? pad(m % 60) : ""}` : `${m}min`;
const addRow = (extra, label) => `<button class="add-row" data-a="quick" ${extra}><span class="plus">${ic("plus", "s")}</span>${esc(label || t("Add task"))}</button>`;

function sortForDay(a, b) {
  const ta = dueTime(a) || "99", tb = dueTime(b) || "99";
  return ta.localeCompare(tb) || (b.priority - a.priority) || byOrder(a, b);
}

/* ------------------------------------------------------------------ views */
let SEL = null;
const EMPTY_ART = `<svg class="art" viewBox="0 0 120 120" aria-hidden="true"><circle cx="60" cy="62" r="40" fill="var(--accent-soft)"/><circle cx="60" cy="62" r="26" fill="none" stroke="var(--accent)" stroke-width="5"/><path d="m48 62 8 8 16-17" fill="none" stroke="var(--accent)" stroke-width="6" stroke-linecap="round" stroke-linejoin="round"/><g fill="var(--due-tom)"><circle cx="20" cy="30" r="3"/><circle cx="100" cy="24" r="4"/><circle cx="104" cy="92" r="2.5"/><circle cx="16" cy="88" r="2"/></g><path d="M92 46l3-7 3 7-3 2z" fill="var(--due-week)"/></svg>`;
const empty = (title, text) => `<div class="empty">${EMPTY_ART}<h3>${esc(title)}</h3><p>${esc(text)}</p></div>`;

function head(title, sub = "", tools = "") {
  document.title = (title ? title + " · " : "") + (S.app.title || BOOT.title || "Coche");
  $("#topbar .title").textContent = title;
  return `<div class="view-head"><h1>${esc(title)}${sub ? `<span class="sub">${sub}</span>` : ""}</h1><div class="tools">${tools}</div></div>`;
}
function ring() {
  const st = S.stats || {}; const g = st.daily_goal || 5, n = st.today || 0;
  const c = 2 * Math.PI * 15, off = c * (1 - Math.min(1, n / g));
  return `<a class="ring" href="${href("/completed")}" data-nav title="${esc(t("{0} of {1} tasks today", n, g))}"><svg viewBox="0 0 38 38"><circle class="bg" cx="19" cy="19" r="15"/><circle class="fg" cx="19" cy="19" r="15" stroke-dasharray="${c}" stroke-dashoffset="${off}"/></svg><span>${n}/${g}</span></a>`;
}

function viewToday() {
  const today = todayS();
  const over = S.tasks.filter(x => dueDay(x) && dueDay(x) < today).sort((a, b) => dueDay(a).localeCompare(dueDay(b)) || b.priority - a.priority);
  const tod = S.tasks.filter(x => dueDay(x) === today).sort(sortForDay);
  let h = head(t("Today"), `${cap(wdShort(todayD()))} ${dm(todayD())}`, ring());
  if (!over.length && !tod.length) return h + addRow(`data-due="${today}"`) + empty(t("You're all done for today!"), t("Enjoy the rest of your day."));
  if (over.length) h += `<section class="group" data-g="over"><div class="group-h"><button class="caret" data-a="group">${ic("down", "s")}</button><span class="gname">${t("Overdue")}</span><span class="cnt">${over.length}</span><button class="link" data-a="resched">${t("Reschedule")}</button></div><ul class="list">${over.map(x => taskHTML(x, { showProject: true })).join("")}</ul></section>`;
  h += `<section class="group" data-g="today">${over.length ? `<div class="group-h"><span class="gname">${cap(wdShort(todayD()))} ${dm(todayD())} · ${t("Today")}</span><span class="cnt">${tod.length}</span></div>` : ""}<ul class="list">${tod.map(x => taskHTML(x, { showProject: true, onlyTime: true })).join("")}</ul>${addRow(`data-due="${today}"`)}</section>`;
  return h;
}

let UP = null;
function weekStart(d) { const sow = +(S.settings.start_of_week || 0); const n = (d.getDay() + 6) % 7; return addDays(d, -((n - sow + 7) % 7)); }
function viewUpcoming() {
  if (!UP) UP = weekStart(todayD());
  const today = todayD(), start = UP < today ? today : UP;
  const month = cap(fmt(UP, { month: "long", year: "numeric" }));
  let h = head(t("Upcoming"), "", `<button class="ib" data-a="up-prev" ${UP <= weekStart(today) ? "disabled" : ""} title="${esc(t("Previous week"))}">${ic("left")}</button><button class="btn ghost" data-a="up-today">${t("Today")}</button><button class="ib" data-a="up-next" title="${esc(t("Next week"))}">${ic("right")}</button>`);
  const days = new Map();
  for (const x of S.tasks) { const d = dueDay(x); if (d) { if (!days.has(d)) days.set(d, []); days.get(d).push(x); } }
  h += `<div class="strip"><span class="month">${esc(month)}</span></div><div class="week" id="weekstrip">`;
  for (let i = 0; i < 7; i++) {
    const d = addDays(UP, i), s = iso(d);
    h += `<button data-a="up-jump" data-day="${s}" class="${s === iso(today) ? "today" : ""}${d < today ? " past" : ""}"><span>${esc(wdShort(d))}</span><b>${d.getDate()}</b>${days.has(s) ? "<i></i>" : ""}</button>`;
  }
  h += `</div>`;
  const over = S.tasks.filter(x => dueDay(x) && dueDay(x) < iso(today));
  if (UP <= today && over.length) h += `<section class="group"><div class="group-h"><button class="caret" data-a="group">${ic("down", "s")}</button><span class="gname">${t("Overdue")}</span><span class="cnt">${over.length}</span><button class="link" data-a="resched">${t("Reschedule")}</button></div><ul class="list">${over.sort((a, b) => dueDay(a).localeCompare(dueDay(b))).map(x => taskHTML(x, { showProject: true })).join("")}</ul></section>`;
  for (let i = 0; i < 21; i++) {
    const d = addDays(start, i), s = iso(d); if (d < UP) continue;
    const list = (days.get(s) || []).sort(sortForDay);
    const n = dayDiff(s);
    const label = `${cap(wdShort(d))} ${dmy(d)}${n === 0 ? " · " + t("Today") : n === 1 ? " · " + t("Tomorrow") : " · " + cap(wdLong(d))}`;
    h += `<section class="group" id="day-${s}"><div class="group-h"><span class="gname">${esc(label)}</span>${list.length ? `<span class="cnt">${list.length}</span>` : ""}</div><ul class="list" data-drop="day" data-day="${s}">${list.map(x => taskHTML(x, { showProject: true, onlyTime: true, drag: true })).join("")}</ul>${addRow(`data-due="${s}"`)}</section>`;
  }
  return h;
}

function viewProject(pid) {
  const p = projById.get(pid);
  if (!p) return head(t("Not found")) + empty(t("This project doesn't exist"), t("It may have been deleted."));
  const board = p.view_style === "board";
  const tools = `<button class="ib" data-a="proj-view" title="${esc(board ? t("List view") : t("Board view"))}">${ic(board ? "list" : "board")}</button>
    <button class="ib" data-a="proj-done" title="${esc(t("Show completed tasks"))}">${ic("done")}</button>
    <button class="ib" data-a="proj-more" data-id="${p.id}" title="${esc(t("More"))}">${ic("more")}</button>`;
  let h = head(projName(p), p.is_archived ? " · " + t("Archived") : "", tools);
  if (p.description) h += `<p class="hint" style="margin:-6px 0 14px">${md(p.description)}</p>`;
  const top = S.tasks.filter(x => x.project_id === pid && !x.parent_id);
  const secs = S.sections.filter(s => s.project_id === pid).sort((a, b) => a.section_order - b.section_order);
  const ctx = { nest: true, drag: true };
  const none = top.filter(x => !x.section_id).sort(byOrder);
  const groups = [{ id: "", name: null, tasks: none }, ...secs.map(s => ({ id: s.id, name: s.name, s, tasks: top.filter(x => x.section_id === s.id).sort(byOrder) }))];
  if (board) {
    h += `<div class="board">` + groups.filter(g => g.id || g.tasks.length || !secs.length).map(g => `<div class="col group${g.s && g.s.is_collapsed ? " closed" : ""}">
      <div class="group-h"><span class="gname">${esc(g.name || t("(No section)"))}</span><span class="cnt">${g.tasks.length}</span>${g.s ? `<button class="ib" data-a="sec-more" data-id="${g.s.id}">${ic("more", "s")}</button>` : ""}</div>
      <ul class="list" data-drop="section" data-project="${pid}" data-section="${g.id}">${g.tasks.map(x => taskHTML(x, { drag: true })).join("")}</ul>
      ${addRow(`data-project="${pid}" data-section="${g.id}"`)}</div>`).join("") +
      `<div class="col"><button class="add-row" data-a="sec-add" data-project="${pid}"><span class="plus">${ic("plus", "s")}</span>${t("Add section")}</button></div></div>`;
  } else {
    h += groups.map((g, i) => {
      if (!g.name) return `<div class="list-zone"><ul class="list" data-drop="section" data-project="${pid}" data-section="">${g.tasks.map(x => taskHTML(x, ctx)).join("")}</ul>${addRow(`data-project="${pid}"`)}<button class="add-section" data-a="sec-add" data-project="${pid}" data-order="0">${t("Add section")}</button></div>`;
      return `<section class="group list-zone${g.s.is_collapsed ? " closed" : ""}" data-section-id="${g.id}"><div class="group-h"><button class="caret" data-a="sec-toggle" data-id="${g.id}">${ic("down", "s")}</button><span class="gname">${esc(g.name)}</span><span class="cnt">${g.tasks.length || ""}</span><button class="ib" data-a="sec-more" data-id="${g.id}">${ic("more", "s")}</button></div>
        <ul class="list" data-drop="section" data-project="${pid}" data-section="${g.id}">${g.tasks.map(x => taskHTML(x, ctx)).join("")}</ul>${addRow(`data-project="${pid}" data-section="${g.id}"`)}
        <button class="add-section" data-a="sec-add" data-project="${pid}" data-order="${g.s.section_order + 1}">${t("Add section")}</button></section>`;
    }).join("");
    if (!top.length && !secs.length) h += empty(t("Nothing here yet"), p.is_inbox_project ? t("Tasks without a project land here. Press Q to add one.") : t("Add a task or a section to get started."));
  }
  if (DONE_CACHE[pid]) {
    const items = DONE_CACHE[pid];
    h += `<section class="group"><div class="group-h"><span class="gname">${t("Completed")}</span><span class="cnt">${items.length}</span></div><ul class="list">${items.map(x => taskHTML(x, { done: true })).join("") || `<p class="hint">${t("No completed tasks in the last 90 days.")}</p>`}</ul></section>`;
  }
  return h;
}
const DONE_CACHE = {};

function viewLabel(name) {
  const items = S.tasks.filter(x => x.labels.some(l => l.toLowerCase() === name.toLowerCase())).sort((a, b) => (dueDay(a) || "9").localeCompare(dueDay(b) || "9") || b.priority - a.priority);
  return head("@" + name) + (items.length ? `<ul class="list">${items.map(x => taskHTML(x, { showProject: true })).join("")}</ul>` : empty(t("No tasks with this label"), t("Add @{0} to a task to see it here.", name))) + addRow(`data-labels="${esc(name)}"`);
}

const FILTER_CACHE = {};
function viewFilter(fid) {
  const f = S.filters.find(x => x.id === fid);
  if (!f) return head(t("Not found")) + empty(t("This filter doesn't exist"), "");
  const tools = `<button class="ib" data-a="filter-edit" data-id="${f.id}" title="${esc(t("Edit"))}">${ic("edit")}</button>`;
  let h = head(f.name, "", tools) + `<p class="hint" style="margin:-8px 0 12px"><code>${esc(f.query)}</code></p>`;
  const c = FILTER_CACHE[fid];
  if (!c || c.stale) {
    api("GET", "/api/v1/tasks/filter?limit=200&query=" + encodeURIComponent(f.query)).then(r => { FILTER_CACHE[fid] = { items: r.results.map(x => x.id) }; if (R.view === "filter" && R.id === fid) renderView(); }).catch(e => { FILTER_CACHE[fid] = { error: e.message }; renderView(); });
    if (!c) return h + `<div class="loading"><div class="spin"></div></div>`;
  }
  if (c.error) return h + empty(t("This filter has an error"), c.error);
  const items = c.items.map(id => byId.get(id)).filter(Boolean);
  return h + (items.length ? `<ul class="list">${items.map(x => taskHTML(x, { showProject: true })).join("")}</ul>` : empty(t("No tasks match this filter"), ""));
}

function viewSearch() {
  const q = R.q || "";
  let h = head(t("Search")) + `<div class="search-bar">${ic("search")}<input id="search-input" type="search" value="${esc(q)}" placeholder="${esc(t("Search tasks, or type a filter like p1 | today"))}" autocomplete="off" enterkeyhint="search"></div>`;
  if (!q.trim()) return h + `<p class="hint">${t("Tip: press / anywhere to search. Filters work here too: today, overdue, p1, @label, #Project, 7 days, no date.")}</p>`;
  const f = fold(q);
  const projects = S.projects.filter(p => fold(p.name).includes(f));
  let items = S.tasks.filter(x => fold(x.content + " " + x.description).includes(f));
  if (SEARCH_FILTER.q === q && SEARCH_FILTER.ids) { const extra = SEARCH_FILTER.ids.map(id => byId.get(id)).filter(Boolean); items = [...new Map([...items, ...extra].map(x => [x.id, x])).values()]; }
  else { SEARCH_FILTER.q = q; SEARCH_FILTER.ids = null; api("GET", "/api/v1/tasks/filter?limit=200&query=" + encodeURIComponent(q)).then(r => { if (SEARCH_FILTER.q === q) { SEARCH_FILTER.ids = r.results.map(x => x.id); if (r.results.length && R.view === "search") renderView(true); } }).catch(() => { SEARCH_FILTER.ids = []; }); }
  if (projects.length) h += `<div class="group"><div class="group-h"><span class="gname">${t("Projects")}</span></div><nav class="nav">${projects.map(p => `<a href="${href("/project/" + p.id)}" data-nav><span class="ico"><i class="dot" style="background:${col(p.color)}"></i></span><span class="lbl">${esc(projName(p))}</span></a>`).join("")}</nav></div>`;
  h += `<div class="group"><div class="group-h"><span class="gname">${t("Tasks")}</span><span class="cnt">${items.length}</span></div><ul class="list">${items.map(x => taskHTML(x, { showProject: true })).join("")}</ul></div>`;
  if (!items.length && !projects.length) h += empty(t("No results"), t("Nothing matches “{0}”.", q));
  return h;
}
const SEARCH_FILTER = { q: null, ids: null };

let ACTIVITY = null;
function viewCompleted() {
  const st = S.stats || {};
  let h = head(t("Completed"));
  const max = Math.max(st.daily_goal || 1, ...(st.days || []).map(d => d.completed));
  h += `<div class="stats-card"><div class="kpis">
    <div class="kpi"><b>${st.today || 0}<small style="font-size:13px;color:var(--fg-3)">/${st.daily_goal || 5}</small></b><span>${t("Today")}</span></div>
    <div class="kpi"><b>${st.week || 0}<small style="font-size:13px;color:var(--fg-3)">/${st.weekly_goal || 25}</small></b><span>${t("This week")}</span></div>
    <div class="kpi"><b><span style="color:var(--due-tom)">${ic("flame", "s")}</span> ${st.streak || 0}</b><span>${t("Day streak")}</span></div>
    <div class="kpi"><b>${st.best_streak || 0}</b><span>${t("Best streak")}</span></div>
    <div class="kpi"><b>${st.completed_total || 0}</b><span>${t("All time")}</span></div></div>
    <div class="bars">${(st.days || []).map(d => `<div title="${esc(dm(D(d.date)))} · ${d.completed}"><i class="${d.completed >= (st.daily_goal || 5) ? "goal" : d.completed ? "" : "low"}" style="height:${Math.max(3, d.completed / max * 100)}%"></i><span>${esc(wdShort(D(d.date)).slice(0, 2))}</span></div>`).join("")}</div></div>`;
  if (!ACTIVITY) { api("GET", "/api/coche/activity?event_type=completed&limit=300").then(r => { ACTIVITY = r.events; if (R.view === "completed") renderView(true); }); return h + `<div class="loading"><div class="spin"></div></div>`; }
  if (!ACTIVITY.length) return h + empty(t("Nothing completed yet"), t("Completed tasks show up here."));
  const groups = new Map();
  for (const e of ACTIVITY) { const d = iso(new Date(e.event_date)); if (!groups.has(d)) groups.set(d, []); groups.get(d).push(e); }
  for (const [d, list] of groups) {
    h += `<section class="group"><div class="group-h"><span class="gname">${esc(dayLabel(d) === t("Today") || dayLabel(d) === t("Yesterday") ? dayLabel(d) + " · " + dm(D(d)) : cap(wdShort(D(d))) + " " + dmy(D(d)))}</span><span class="cnt">${list.length}</span></div><ul class="list">` +
      list.map(e => { const p = projById.get(e.parent_project_id); const tm = new Date(e.event_date); return `<li class="task done-row"><div class="row"><span class="check done" style="--pc:var(--ok)">${ic("check")}</span><div class="body"><div class="content">${md(e.content || "")}</div><div class="meta"><span>${hm(pad(tm.getHours()) + ":" + pad(tm.getMinutes()))}</span>${e.extra_data && e.extra_data.recurring ? `<span>${ic("repeat", "xs")}</span>` : ""}${p ? `<span class="proj">${esc(projName(p))} <i class="dot" style="background:${col(p.color)}"></i></span>` : ""}</div></div>${e.extra_data && !e.extra_data.recurring && e.object_id ? `<button class="ib" data-a="undo-done" data-id="${e.object_id}" title="${esc(t("Uncomplete"))}">${ic("repeat", "s")}</button>` : ""}</div></li>`; }).join("") + `</ul></section>`;
  }
  return h;
}

function viewLabels() {
  let h = head(t("Filters & labels"));
  h += `<section class="group"><div class="group-h"><span class="gname">${t("My filters")}</span><button class="ib" data-a="filter-add" title="${esc(t("Add filter"))}">${ic("plus", "s")}</button></div>`;
  h += S.filters.length ? S.filters.map(f => `<div class="item-line"><span style="color:${col(f.color)}">${ic("grid", "s")}</span><a class="grow" href="${href("/filter/" + f.id)}" data-nav style="color:inherit;text-decoration:none">${esc(f.name)}<div class="q">${esc(f.query)}</div></a><button class="ib" data-a="filter-edit" data-id="${f.id}">${ic("edit", "s")}</button></div>`).join("")
    : `<p class="hint">${t("Filters are saved searches: “today | overdue”, “p1 & #Work”, “@errand”, “7 days & !@waiting”…")}</p>`;
  h += `</section><section class="group"><div class="group-h"><span class="gname">${t("Labels")}</span><button class="ib" data-a="label-add" title="${esc(t("Add label"))}">${ic("plus", "s")}</button></div>`;
  h += S.labels.length ? S.labels.map(l => { const n = S.tasks.filter(x => x.labels.includes(l.name)).length; return `<div class="item-line"><span style="color:${col(l.color)}">${ic("tag", "s")}</span><a class="grow" href="${href("/label/" + encodeURIComponent(l.name))}" data-nav style="color:inherit;text-decoration:none">${esc(l.name)}</a><span class="hint" style="margin:0">${n || ""}</span><button class="ib" data-a="label-edit" data-id="${l.id}">${ic("edit", "s")}</button></div>`; }).join("")
    : `<p class="hint">${t("Type @label in a task to create one.")}</p>`;
  h += `</section>`;
  if (S.archived_projects.length) h += `<section class="group"><div class="group-h"><span class="gname">${t("Archived projects")}</span></div>${S.archived_projects.map(p => `<div class="item-line"><i class="dot" style="background:${col(p.color)}"></i><a class="grow" href="${href("/project/" + p.id)}" data-nav style="color:inherit;text-decoration:none">${esc(p.name)}</a><button class="btn ghost" data-a="proj-unarchive" data-id="${p.id}">${t("Unarchive")}</button></div>`).join("")}</section>`;
  return h;
}

function viewSettings() {
  const s = S.settings, a = S.app || {};
  const opt = (v, cur, label) => `<option value="${esc(v)}"${String(v) === String(cur) ? " selected" : ""}>${esc(label)}</option>`;
  const days = [0, 1, 2, 3, 4, 5, 6].map(i => ({ i, name: fmt(addDays(new Date(2024, 0, 1), i), { weekday: "short" }) }));
  let h = head(t("Settings"));
  h += `<div class="set-sec"><h2>${ic("globe", "s")}${t("General")}</h2><div class="form">
    <div class="row2"><label>${t("Language")}<select data-set="lang">${opt("auto", s.lang, t("Automatic"))}${opt("en", s.lang, "English")}${opt("fr", s.lang, "Français")}</select></label>
    <label>${t("Theme")}<select data-set="theme">${opt("auto", s.theme, t("Automatic"))}${opt("light", s.theme, t("Light"))}${opt("dark", s.theme, t("Dark"))}</select></label></div>
    <div class="row2"><label>${t("Date format")}<select data-set="date_order">${opt("DMY", s.date_order, "31/12")}${opt("MDY", s.date_order, "12/31")}</select></label>
    <label>${t("Time format")}<select data-set="time_format">${opt("24h", s.time_format, "13:00")}${opt("12h", s.time_format, "1pm")}</select></label></div>
    <div class="row2"><label>${t("Week starts on")}<select data-set="start_of_week" data-num>${days.map(d => opt(d.i, s.start_of_week, cap(d.name))).join("")}</select></label>
    <label>${t("Accent colour")}<input type="color" data-set="accent" value="${esc(s.accent || "#dc4c3e")}" style="height:40px;padding:2px;border-radius:9px;border:1px solid var(--line-2);background:var(--bg);width:100%"></label></div>
    <label class="switch">${t("Completion sound")}<input type="checkbox" data-set="sound" ${s.sound ? "checked" : ""}></label></div></div>`;
  h += `<div class="set-sec"><h2>${ic("chart", "s")}${t("Goals")}</h2><div class="form"><div class="row2">
    <label>${t("Daily goal")}<input type="number" min="1" max="100" data-set="daily_goal" data-num value="${s.daily_goal}"></label>
    <label>${t("Weekly goal")}<input type="number" min="1" max="700" data-set="weekly_goal" data-num value="${s.weekly_goal}"></label></div>
    <label>${t("Days off (your streak is kept on these days)")}<div style="display:flex;gap:6px;flex-wrap:wrap">${days.map(d => `<button class="tag${(s.days_off || []).includes(d.i) ? " on" : ""}" data-a="dayoff" data-day="${d.i}">${esc(cap(d.name))}</button>`).join("")}</div></label></div></div>`;
  h += `<div class="set-sec"><h2>${ic("bell", "s")}${t("Reminders")}</h2><div class="form"><div class="row2">
    <label>${t("Automatic reminder for timed tasks")}<select data-set="auto_reminder" data-num data-null>${opt("", s.auto_reminder ?? "", t("None"))}${[0, 5, 10, 15, 30, 60].map(m => opt(m, s.auto_reminder ?? "", m ? t("{0} min before", m) : t("At the time of the task"))).join("")}</select></label>
    <label>${t("Reminder time for tasks without a time")}<input type="time" data-set="reminder_time" value="${esc(s.reminder_time || "09:00")}"></label></div>
    <p>${(a.notifications || []).length ? t("Notifications are sent through: {0}.", a.notifications.join(", ")) : t("No notification channel is configured on the server yet (COCHE_NTFY_URL, COCHE_NOTIFY_COMMAND or COCHE_WEBHOOK_URL).")}</p>
    <div><button class="btn" data-a="notify-test">${ic("zap", "s")}${t("Send a test notification")}</button></div></div></div>`;
  h += `<div class="set-sec"><h2>${ic("cal", "s")}${t("Calendar feed")}</h2><p>${t("Subscribe from Apple Calendar, Google Calendar or Thunderbird to see your dated tasks there.")}</p><div class="code" id="ics-url">${esc(location.origin + (a.calendar_url || ""))}</div><div style="margin-top:8px"><button class="btn" data-a="copy" data-target="ics-url">${ic("copy", "s")}${t("Copy")}</button></div></div>`;
  h += `<div class="set-sec"><h2>${ic("ul", "s")}${t("Import & backup")}</h2><p>${t("Move from Todoist in one click: paste your Todoist API token (Todoist › Settings › Integrations › Developer). It is used once and never stored.")}</p>
    <div class="form"><label>${t("Todoist API token")}<input type="password" id="td-token" autocomplete="off" placeholder="0123abcd…"></label></div>
    <div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:10px"><button class="btn primary" data-a="import-todoist">${t("Import from Todoist")}</button>
    <button class="btn" data-a="export">${ic("dl", "s")}${t("Download a backup")}</button>
    <label class="btn" style="cursor:pointer">${ic("ul", "s")}${t("Restore a backup")}<input type="file" accept="application/json" id="restore-file" hidden></label></div><p id="import-res" class="hint"></p></div>`;
  h += `<div class="set-sec"><h2>${ic("key", "s")}${t("API & integrations")}</h2><p>${t("Coche speaks the Todoist API v1: point any Todoist script at {0} and it just works.", `<code>${esc(location.origin + BASE)}/api/v1/</code>`)}</p>${a.protected ? `<div id="tokens"></div><button class="btn" data-a="token-add">${ic("plus", "s")}${t("New API token")}</button>` : `<p>${t("No password is set, so the API is open to anyone who can reach this server. Set COCHE_PASSWORD to require tokens.")}</p>`}</div>`;
  h += `<div class="set-sec"><h2>${ic("sliders", "s")}${t("Keyboard shortcuts")}</h2><button class="btn" data-a="shortcuts">${t("Show shortcuts")}</button>${a.protected ? ` <button class="btn danger" data-a="logout">${ic("logout", "s")}${t("Log out")}</button>` : ""}</div>`;
  h += `<p class="hint" style="text-align:center">Coche ${esc(a.version || BOOT.version || "")} · <a href="https://github.com/mathyouadr/coche" target="_blank" rel="noopener">GitHub</a> · MIT</p>`;
  if (a.protected) setTimeout(loadTokens, 0);
  return h;
}
async function loadTokens() {
  const el = $("#tokens"); if (!el) return;
  const list = await api("GET", "/api/coche/tokens");
  el.innerHTML = list.map(x => `<div class="item-line"><span>${ic("key", "s")}</span><span class="grow">${esc(x.name)}<div class="q">${t("last used")}: ${x.last_used_at ? esc(new Date(x.last_used_at).toLocaleString(locale())) : t("never")}</div></span><button class="ib" data-a="token-del" data-id="${x.id}">${ic("trash", "s")}</button></div>`).join("") || `<p class="hint">${t("No token yet.")}</p>`;
}

/* ------------------------------------------------------------------ sidebar */
function renderSidebar() {
  const today = todayS();
  const nToday = S.tasks.filter(x => dueDay(x) && dueDay(x) <= today).length;
  const count = pid => S.tasks.filter(x => x.project_id === pid).length || "";
  const on = (v, id) => R.view === v && (id === undefined || R.id === id) ? " on" : "";
  const ib = inbox();
  const favP = S.projects.filter(p => p.is_favorite && !p.is_inbox_project), favL = S.labels.filter(l => l.is_favorite), favF = S.filters.filter(f => f.is_favorite);
  const tree = (parent, depth) => S.projects.filter(p => !p.is_inbox_project && (p.parent_id || null) === parent).sort((a, b) => a.child_order - b.child_order)
    .map(p => `<a class="${on("project", p.id)}" href="${href("/project/" + p.id)}" data-nav style="padding-left:${8 + depth * 18}px"><span class="ico">${ic("hash", "s").replace('class="i s"', `class="i s" style="color:${col(p.color)}"`)}</span><span class="lbl">${esc(p.name)}</span><span class="n">${count(p.id)}</span><button class="ib proj-more" data-a="proj-more" data-id="${p.id}">${ic("more", "s")}</button></a>` + tree(p.id, depth + 1)).join("");
  $("#sidebar").innerHTML = `
    <div class="side-top"><div class="brand"><span class="logo">${ic("check")}</span>${esc(S.app.title || BOOT.title || "Coche")}</div>
      <button class="ib" data-a="search" title="${esc(t("Search"))} (/)">${ic("search")}</button>
      <button class="ib desk-only" data-a="nav-collapse" title="${esc(t("Hide sidebar"))}">${ic("sidebar")}</button></div>
    <button class="side-add" data-a="quick">${`<span class="plus">${ic("plus")}</span>`}${t("Add task")}</button>
    <div class="side-scroll"><nav class="nav">
      <a class="${on("inbox")}" href="${href("/inbox")}" data-nav><span class="ico inbox">${ic("inbox")}</span><span class="lbl">${t("Inbox")}</span><span class="n">${count(ib.id)}</span></a>
      <a class="${on("today")}" href="${href("/today")}" data-nav><span class="ico today">${todayIcon(todayD().getDate())}</span><span class="lbl">${t("Today")}</span><span class="n">${nToday || ""}</span></a>
      <a class="${on("upcoming")}" href="${href("/upcoming")}" data-nav><span class="ico up">${ic("up")}</span><span class="lbl">${t("Upcoming")}</span></a>
      <a class="${on("labels")}" href="${href("/labels")}" data-nav><span class="ico flt">${ic("grid")}</span><span class="lbl">${t("Filters & labels")}</span></a>
      <a class="${on("completed")}" href="${href("/completed")}" data-nav><span class="ico done">${ic("done")}</span><span class="lbl">${t("Completed")}</span></a>
    </nav>
    ${favP.length + favL.length + favF.length ? `<div class="side-h">${t("Favorites")}</div><nav class="nav">${favP.map(p => `<a class="${on("project", p.id)}" href="${href("/project/" + p.id)}" data-nav><span class="ico"><i class="dot" style="background:${col(p.color)}"></i></span><span class="lbl">${esc(p.name)}</span><span class="n">${count(p.id)}</span></a>`).join("")}${favF.map(f => `<a class="${on("filter", f.id)}" href="${href("/filter/" + f.id)}" data-nav><span class="ico" style="color:${col(f.color)}">${ic("grid", "s")}</span><span class="lbl">${esc(f.name)}</span></a>`).join("")}${favL.map(l => `<a class="${on("label", l.name)}" href="${href("/label/" + encodeURIComponent(l.name))}" data-nav><span class="ico" style="color:${col(l.color)}">${ic("tag", "s")}</span><span class="lbl">${esc(l.name)}</span></a>`).join("")}</nav>` : ""}
    <div class="side-h">${t("My projects")}<button class="ib" data-a="proj-add" title="${esc(t("Add project"))}">${ic("plus", "s")}</button></div>
    <nav class="nav">${tree(null, 0) || `<p class="hint" style="padding:0 8px">${t("No project yet.")}</p>`}</nav></div>
    <div class="side-foot"><nav class="nav"><a class="${on("settings")}" href="${href("/settings")}" data-nav><span class="ico">${ic("sliders")}</span><span class="lbl">${t("Settings")}</span></a></nav></div>`;
}

/* ------------------------------------------------------------------ render */
function renderView(keepScroll) {
  const v = $("#view"), top = v.scrollTop;
  let h;
  switch (R.view) {
    case "inbox": h = viewProject(inbox().id); break;
    case "project": h = viewProject(R.id); break;
    case "upcoming": h = viewUpcoming(); break;
    case "label": h = viewLabel(R.id); break;
    case "filter": h = viewFilter(R.id); break;
    case "search": h = viewSearch(); break;
    case "completed": h = viewCompleted(); break;
    case "labels": h = viewLabels(); break;
    case "settings": h = viewSettings(); break;
    default: h = viewToday();
  }
  const active = document.activeElement && document.activeElement.id === "search-input" ? document.activeElement.selectionStart : null;
  v.innerHTML = `<div class="wrap">${h}</div>`;
  if (keepScroll !== false) v.scrollTop = top;
  if (active !== null) { const i = $("#search-input"); if (i) { i.focus(); i.setSelectionRange(active, active); } }
  if (R.view === "search" && active === null && !R.q) { const i = $("#search-input"); if (i) i.focus(); }
}
function render(quiet) {
  renderSidebar(); renderView();
  if (DETAIL && byId.has(DETAIL) && !quiet) renderDetail();
  else if (DETAIL && !byId.has(DETAIL) && !quiet) closeDetail();
}

/* ------------------------------------------------------------------ toasts, menus, modals */
let toastTimer = null;
function toast(msg, undo, label) {
  const el = $("#toast");
  el.innerHTML = `<span>${esc(msg)}</span>${undo ? `<button>${esc(label || t("Undo"))}</button>` : ""}`;
  if (undo) el.querySelector("button").onclick = () => { el.classList.remove("show"); undo(); };
  el.classList.add("show"); clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.remove("show"), undo ? 6000 : 3500);
}
let POP = null;
function closePop() { if (POP) { POP.el.remove(); POP.onclose && POP.onclose(); POP = null; } }
function pop(anchor, html, opts = {}) {
  closePop();
  const el = document.createElement("div");
  el.className = "pop" + (opts.sheet !== false ? " sheetish" : "");
  el.innerHTML = html; document.body.append(el);
  const r = anchor && anchor.getBoundingClientRect ? anchor.getBoundingClientRect() : { left: innerWidth / 2 - 150, bottom: innerHeight / 3, top: innerHeight / 3 };
  const w = el.offsetWidth, h = el.offsetHeight;
  let x = Math.min(Math.max(8, r.left), innerWidth - w - 8), y = r.bottom + 6;
  if (y + h > innerHeight - 8) y = Math.max(8, r.top - h - 6);
  el.style.left = x + "px"; el.style.top = y + "px";
  POP = { el, onclose: opts.onclose };
  setTimeout(() => { const f = el.querySelector("input.txt, [autofocus]"); if (f && matchMedia("(hover: hover)").matches) f.focus(); }, 30);
  return el;
}
document.addEventListener("pointerdown", e => { if (POP && !POP.el.contains(e.target) && !e.target.closest("[data-keep-pop]")) closePop(); }, true);
function menu(anchor, items) {
  const el = pop(anchor, items.map((it, i) => it === "-" ? `<div class="sep"></div>` : it.head ? `<div class="ph">${esc(it.head)}</div>` : `<button class="mi${it.on ? " on" : ""}" data-i="${i}" style="${it.danger ? "color:var(--due-over)" : ""}">${it.icon || ""}<span>${esc(it.label)}</span>${it.right ? `<span class="r">${esc(it.right)}</span>` : ""}</button>`).join(""));
  el.addEventListener("click", e => { const b = e.target.closest(".mi"); if (!b) return; const it = items[+b.dataset.i]; closePop(); it.run && run(it.run)(); });
}
function modal(html, onOpen) {
  return new Promise(resolve => {
    const scrim = document.createElement("div"); scrim.className = "modal-scrim";
    const el = document.createElement("div"); el.className = "modal"; el.setAttribute("role", "dialog"); el.innerHTML = html;
    document.body.append(scrim, el);
    const done = v => { scrim.remove(); el.remove(); MODAL = null; resolve(v); };
    MODAL = { close: () => done(null) };
    scrim.onclick = () => done(null);
    onOpen && onOpen(el, done);
    const f = el.querySelector("input:not([type=hidden]), textarea, select"); if (f) setTimeout(() => f.focus(), 30);
  });
}
let MODAL = null;
function confirmBox(title, text, ok, danger = true) {
  return modal(`<h3>${esc(title)}</h3><p style="color:var(--fg-2);margin:0">${esc(text)}</p><div class="acts"><button class="btn ghost" data-r="0">${t("Cancel")}</button><button class="btn ${danger ? "primary" : "primary"}" data-r="1">${esc(ok)}</button></div>`,
    (el, done) => el.addEventListener("click", e => { const b = e.target.closest("[data-r]"); if (b) done(b.dataset.r === "1"); }));
}
function colorPicker(name, cur) {
  return `<div class="colors" data-colors="${name}">${Object.entries(COLORS).map(([k, v]) => `<button type="button" title="${k}" data-color="${k}" class="${k === (cur || "charcoal") ? "on" : ""}" style="background:${v}"></button>`).join("")}<input type="hidden" name="${name}" value="${esc(cur || "charcoal")}"></div>`;
}
function formBox(title, fields, okLabel, extraBtn) {
  const f = fields.map(x => {
    if (x.type === "color") return `<label>${esc(x.label)}${colorPicker(x.name, x.value)}</label>`;
    if (x.type === "switch") return `<label class="switch">${esc(x.label)}<input type="checkbox" name="${x.name}" ${x.value ? "checked" : ""}></label>`;
    if (x.type === "select") return `<label>${esc(x.label)}<select name="${x.name}">${x.options.map(o => `<option value="${esc(o.value)}"${o.value === x.value ? " selected" : ""}>${esc(o.label)}</option>`).join("")}</select></label>`;
    if (x.type === "textarea") return `<label>${esc(x.label)}<textarea name="${x.name}" rows="3" placeholder="${esc(x.placeholder || "")}">${esc(x.value || "")}</textarea></label>`;
    return `<label>${esc(x.label)}<input type="text" name="${x.name}" value="${esc(x.value || "")}" placeholder="${esc(x.placeholder || "")}" ${x.required ? "required" : ""} autocomplete="off">${x.hint ? `<span class="hint" style="font-weight:400">${x.hint}</span>` : ""}</label>`;
  }).join("");
  return modal(`<h3>${esc(title)}</h3><form class="form">${f}<div class="acts">${extraBtn ? `<button type="button" class="btn danger ghost" data-r="extra" style="margin-right:auto">${esc(extraBtn)}</button>` : ""}<button type="button" class="btn ghost" data-r="0">${t("Cancel")}</button><button class="btn primary" type="submit">${esc(okLabel || t("Save"))}</button></div></form>`, (el, done) => {
    el.addEventListener("click", e => {
      const c = e.target.closest("[data-color]");
      if (c) { e.preventDefault(); const w = c.closest("[data-colors]"); $$("button", w).forEach(b => b.classList.toggle("on", b === c)); w.querySelector("input").value = c.dataset.color; }
      const b = e.target.closest("[data-r]"); if (b) done(b.dataset.r === "extra" ? "extra" : null);
    });
    el.querySelector("form").addEventListener("submit", e => {
      e.preventDefault(); const out = {};
      for (const x of fields) { const i = el.querySelector(`[name="${x.name}"]`); out[x.name] = x.type === "switch" ? i.checked : i.value.trim(); }
      done(out);
    });
  });
}

/* ------------------------------------------------------------------ pickers */
function dateSpecLabel(spec) {
  if (!spec) return null;
  if (spec.label) return spec.label;
  if (spec.due_date) return dayLabel(spec.due_date) + (spec.due_time ? " " + hm(spec.due_time) : "");
  return spec.due_string;
}
function datePicker(anchor, cur, cb) {
  // cur: {date: "YYYY-MM-DD", time, recurring, string}
  const td = todayD();
  const sat = addDays(td, (6 - td.getDay() + 7) % 7 || (td.getDay() === 6 ? 0 : 7));
  const mon = addDays(td, ((8 - td.getDay()) % 7) || 7);
  const quick = [
    { icon: "sun", c: "var(--due-today)", label: t("Today"), d: td },
    { icon: "sun", c: "var(--due-tom)", label: t("Tomorrow"), d: addDays(td, 1) },
    { icon: "sofa", c: "var(--p3)", label: td.getDay() === 6 || td.getDay() === 0 ? t("Next weekend") : t("This weekend"), d: td.getDay() === 0 ? addDays(td, 6) : td.getDay() === 6 ? addDays(td, 7) : sat },
    { icon: "arrow", c: "var(--due-week)", label: t("Next week"), d: mon },
  ];
  let month = cur && cur.date ? D(cur.date) : td; month = new Date(month.getFullYear(), month.getMonth(), 1);
  const sel = cur && cur.date;
  const calHTML = () => {
    const first = month, sow = +(S.settings.start_of_week || 0);
    const off = ((first.getDay() + 6) % 7 - sow + 7) % 7;
    const n = new Date(first.getFullYear(), first.getMonth() + 1, 0).getDate();
    let g = [0, 1, 2, 3, 4, 5, 6].map(i => `<span class="wd">${esc(fmt(addDays(new Date(2024, 0, 1), (i + sow) % 7), { weekday: "narrow" }))}</span>`).join("");
    for (let i = 0; i < off; i++) g += `<button class="other" tabindex="-1"></button>`;
    for (let d = 1; d <= n; d++) { const x = new Date(first.getFullYear(), first.getMonth(), d), s = iso(x); g += `<button data-day="${s}" class="${s === iso(td) ? "today" : ""}${s === sel ? " sel" : ""}${x < td ? " past" : ""}">${d}</button>`; }
    return `<div class="cal-h"><button class="ib" data-m="-1" data-keep-pop>${ic("left", "s")}</button><span>${esc(fmt(month, { month: "long", year: "numeric" }))}</span><button class="ib" data-m="1">${ic("right", "s")}</button></div><div class="cal-g">${g}</div>`;
  };
  const el = pop(anchor, `<div class="pad"><input class="txt" id="dp-txt" placeholder="${esc(t("Type a date: thu 2pm, every monday…"))}" value="${esc(cur && cur.recurring ? cur.string : "")}" autocomplete="off" enterkeyhint="done"><div class="preview" id="dp-prev">${cur && cur.recurring ? ic("repeat", "xs") + " " + esc(cur.string) : ""}</div></div>
    ${quick.map((q, i) => `<button class="mi" data-q="${i}"><span style="color:${q.c}">${ic(q.icon, "s")}</span><span>${esc(q.label)}</span><span class="r">${esc(cap(wdShort(q.d)))}${dayDiff(iso(q.d)) > 1 ? " " + dm(q.d) : ""}</span></button>`).join("")}
    ${cur && cur.date ? `<button class="mi" data-q="none"><span style="color:var(--fg-3)">${ic("ban", "s")}</span><span>${t("No date")}</span></button>` : ""}
    <div class="sep"></div><div class="cal" id="dp-cal">${calHTML()}</div>
    <div class="time-row">${ic("clock", "s")}<input type="time" id="dp-time" value="${esc(cur && cur.time || "")}"><span class="hint" style="margin:0">${t("optional")}</span></div>`);
  const timeVal = () => $("#dp-time", el).value || null;
  const done = spec => { closePop(); cb(spec); };
  el.addEventListener("click", e => {
    const m = e.target.closest("[data-m]"); if (m) { e.stopPropagation(); month = new Date(month.getFullYear(), month.getMonth() + +m.dataset.m, 1); $("#dp-cal", el).innerHTML = calHTML(); return; }
    const d = e.target.closest("[data-day]"); if (d) return done({ due_date: d.dataset.day, due_time: timeVal() });
    const q = e.target.closest("[data-q]"); if (!q) return;
    if (q.dataset.q === "none") return done({ due_string: "no date", label: t("No date") });
    done({ due_date: iso(quick[+q.dataset.q].d), due_time: timeVal() });
  });
  const txt = $("#dp-txt", el), prev = $("#dp-prev", el); let seq = 0, last = null;
  txt.addEventListener("input", async () => {
    const my = ++seq, v = txt.value.trim();
    if (!v) { prev.textContent = ""; last = null; return; }
    const r = await api("POST", "/api/coche/parse", { text: v, lang: LANG }).catch(() => null);
    if (my !== seq || !r) return;
    last = r.due && r.due.date ? r : null;
    prev.className = "preview" + (last ? " ok" : "");
    prev.innerHTML = last ? `${ic(last.due.is_recurring ? "repeat" : "cal", "xs")} ${esc(dayLabel(last.due.date))}${last.due.time ? " " + hm(last.due.time) : ""}${last.due.rule_text ? " · " + esc(last.due.rule_text) : ""}` : esc(t("Not understood yet…"));
  });
  txt.addEventListener("keydown", e => { if (e.key === "Enter") { e.preventDefault(); if (last) done({ due_string: txt.value.trim(), label: txt.value.trim() }); } });
  $("#dp-time", el).addEventListener("change", e => { if (cur && cur.date && !e.target.closest(".pop").querySelector(".sel")) return; });
}
function priorityPicker(anchor, cur, cb) {
  menu(anchor, [4, 3, 2, 1].map(p => ({ icon: `<span style="color:var(--${PRIO[p]})">${ic("flag", "s").replace("<path", '<path fill="' + (p < 4 ? "currentColor" : "none") + '"')}</span>`, label: t("Priority {0}", 5 - p), on: cur === p, run: () => cb(p) })));
}
function labelPicker(anchor, cur, cb) {
  let chosen = new Set(cur);
  const list = q => {
    const f = fold(q); const ls = S.labels.filter(l => fold(l.name).includes(f));
    let h = ls.map(l => `<button class="mi" data-l="${esc(l.name)}"><span style="color:${col(l.color)}">${ic("tag", "s")}</span><span>${esc(l.name)}</span><span class="r">${chosen.has(l.name) ? ic("check", "s") : ""}</span></button>`).join("");
    if (q && !S.labels.some(l => fold(l.name) === f)) h += `<button class="mi" data-new="${esc(q)}">${ic("plus", "s")}<span>${t("Create “{0}”", esc(q))}</span></button>`;
    return h || `<p class="hint pad">${t("No labels yet. Type a name to create one.")}</p>`;
  };
  const el = pop(anchor, `<div class="pad"><input class="txt" placeholder="${esc(t("Type a label"))}" autocomplete="off"></div><div class="ll">${list("")}</div>`, { onclose: () => cb([...chosen]) });
  const inp = $("input", el);
  inp.addEventListener("input", () => { $(".ll", el).innerHTML = list(inp.value.trim()); });
  inp.addEventListener("keydown", e => { if (e.key === "Enter") { e.preventDefault(); const v = inp.value.trim().replace(/^@/, "").replace(/\s+/g, "_"); if (v) { chosen.add(S.labels.find(l => fold(l.name) === fold(v))?.name || v); inp.value = ""; $(".ll", el).innerHTML = list(""); } } });
  el.addEventListener("click", e => {
    const b = e.target.closest("[data-l]"), n = e.target.closest("[data-new]");
    if (b) { const v = b.dataset.l; chosen.has(v) ? chosen.delete(v) : chosen.add(v); $(".ll", el).innerHTML = list(inp.value.trim()); }
    if (n) { chosen.add(n.dataset.new.replace(/\s+/g, "_")); inp.value = ""; $(".ll", el).innerHTML = list(""); }
  });
}
function projectPicker(anchor, cur, cb) {
  const items = [];
  const rows = (parent, depth) => S.projects.filter(p => (p.is_inbox_project ? null : p.parent_id || null) === parent && (parent !== null || !p.parent_id)).sort((a, b) => (b.is_inbox_project - a.is_inbox_project) || a.child_order - b.child_order).forEach(p => {
    if (parent === null && p.parent_id) return;
    items.push({ p, s: null, depth });
    S.sections.filter(s => s.project_id === p.id).sort((a, b) => a.section_order - b.section_order).forEach(s => items.push({ p, s, depth: depth + 1 }));
    if (!p.is_inbox_project) rows(p.id, depth + 1);
  });
  rows(null, 0);
  const list = q => items.filter(it => !q || fold(it.p.name + " " + (it.s ? it.s.name : "")).includes(fold(q))).map((it, i) => `<button class="mi${cur.project_id === it.p.id && (cur.section_id || null) === (it.s ? it.s.id : null) ? " on" : ""}" data-p="${it.p.id}" data-s="${it.s ? it.s.id : ""}" style="padding-left:${10 + it.depth * 16}px">${it.s ? `<span style="color:var(--fg-3)">${ic("list", "xs")}</span>` : it.p.is_inbox_project ? `<span style="color:var(--p3)">${ic("inbox", "s")}</span>` : `<i class="dot" style="background:${col(it.p.color)}"></i>`}<span>${esc(it.s ? it.s.name : projName(it.p))}</span></button>`).join("");
  const el = pop(anchor, `<div class="pad"><input class="txt" placeholder="${esc(t("Type a project name"))}" autocomplete="off"></div><div class="pl">${list("")}</div>`);
  const inp = $("input", el);
  inp.addEventListener("input", () => { $(".pl", el).innerHTML = list(inp.value.trim()); });
  el.addEventListener("click", e => { const b = e.target.closest("[data-p]"); if (b) { closePop(); cb({ project_id: b.dataset.p, section_id: b.dataset.s || null }); } });
}
/* Reminders: a panel that stays open, several at once. `ctx`:
   { list(): current reminders [{minutes_before|minute_offset, time, at, id}], add(r), remove(r), due: {day, time} } */
const REM_PRESETS = [0, 5, 15, 30, 60, 120, 180, 1440, 2880, 10080];
function remLabel(r) {
  const m = r.minutes_before ?? r.minute_offset;
  if (r.at) return cap(wdShort(D(r.at))) + " " + dm(D(r.at)) + " " + hm(r.at.slice(11, 16));
  if (r.time) return t("At {0} on the day", hm(r.time));
  if (!m) return t("At the time of the task");
  if (m % 10080 === 0) return plural(m / 10080, "{0} week before", "{0} weeks before");
  if (m % 1440 === 0) return plural(m / 1440, "{0} day before", "{0} days before");
  if (m % 60 === 0) return plural(m / 60, "{0} hour before", "{0} hours before");
  return t("{0} min before", m);
}
function reminderPicker(anchor, ctx) {
  const auto = S.settings.auto_reminder;
  const offsetOf = r => r.minutes_before ?? r.minute_offset;
  const paint = () => {
    const list = ctx.list();
    const has = m => list.some(r => !r.at && !r.time && offsetOf(r) === m);
    const autoOff = has(-1);
    const ref = ctx.due && ctx.due.time ? hm(ctx.due.time) : hm(S.settings.reminder_time || "09:00");
    const fixed = list.filter(r => r.at || r.time);
    const row = (m, label, on, extra = "") => `<button class="mi" data-m="${m}" ${extra}><span style="color:${on ? "var(--accent)" : "var(--fg-3)"}">${ic(on ? "done" : "bell", "s")}</span><span>${esc(label)}</span>${on ? `<span class="r">${ic("check", "s")}</span>` : ""}</button>`;
    let h = `<div class="ph">${esc(t("Tap to add or remove · relative to {0}", ref))}</div>`;
    if (auto !== null && auto !== undefined && ctx.due && ctx.due.time)
      h += row("auto", t("Automatic: {0}", remLabel({ minutes_before: auto })), !autoOff) + `<div class="sep"></div>`;
    h += REM_PRESETS.filter(m => !(auto !== null && auto !== undefined && ctx.due && ctx.due.time && m === auto)).map(m => row(m, remLabel({ minutes_before: m }), has(m))).join("");
    if (fixed.length) h += `<div class="sep"></div>` + fixed.map(r => `<button class="mi" data-del="${esc(r.id || JSON.stringify(r))}"><span style="color:var(--accent)">${ic("clock", "s")}</span><span>${esc(remLabel(r))}</span><span class="r">${ic("x", "s")}</span></button>`).join("");
    h += `<div class="sep"></div><div class="pad" style="display:grid;gap:8px">
      <label class="hint" style="margin:0">${esc(t("At a time on the due day"))}</label>
      <div style="display:flex;gap:6px"><input class="txt" type="time" id="rp-time" value="08:00"><button class="btn" data-add="time">${t("Add")}</button></div>
      <label class="hint" style="margin:0">${esc(t("At a precise date and time"))}</label>
      <div style="display:flex;gap:6px"><input class="txt" type="datetime-local" id="rp-at" value="${esc((ctx.due && ctx.due.day ? iso(addDays(D(ctx.due.day), -1)) : todayS()) + "T20:00")}"><button class="btn" data-add="at">${t("Add")}</button></div></div>`;
    el.innerHTML = h;
  };
  const el = pop(anchor, "", { onclose: ctx.onclose });
  el.style.minWidth = "280px";
  paint();
  const p = el.getBoundingClientRect(); if (p.bottom > innerHeight - 8) el.style.top = Math.max(8, innerHeight - p.height - 8) + "px";
  el.addEventListener("click", run(async e => {
    e.stopPropagation();
    const list = ctx.list(), offsetOf2 = r => r.minutes_before ?? r.minute_offset;
    const b = e.target.closest("[data-m]"), d = e.target.closest("[data-del]"), a = e.target.closest("[data-add]");
    if (b) {
      const m = b.dataset.m === "auto" ? -1 : +b.dataset.m;
      const cur = list.find(r => !r.at && !r.time && offsetOf2(r) === m);
      // the "auto" row is ON when no opt-out (-1) exists: clicking it adds or removes the opt-out
      if (cur) await ctx.remove(cur); else await ctx.add({ minutes_before: m });
    } else if (d) {
      const cur = list.find(r => (r.id || JSON.stringify(r)) === d.dataset.del); if (cur) await ctx.remove(cur);
    } else if (a) {
      if (a.dataset.add === "time") { const v = $("#rp-time", el).value; if (v) await ctx.add({ time: v }); }
      else { const v = $("#rp-at", el).value; if (v) await ctx.add({ at: v.slice(0, 16) }); }
    } else return;
    paint();
  }));
}

/* ------------------------------------------------------------------ actions on tasks */
async function updateTask(id, body) { const x = await api("POST", `/api/v1/tasks/${id}`, body); put(x); render(); return x; }
let soundCtx = null;
function sound() {
  if (!S.settings.sound) return;
  try {
    soundCtx = soundCtx || new (window.AudioContext || window.webkitAudioContext)();
    const A = soundCtx, o = A.createOscillator(), g = A.createGain(), n = A.currentTime;
    o.type = "sine"; o.frequency.setValueAtTime(740, n); o.frequency.exponentialRampToValueAtTime(1480, n + .09);
    g.gain.setValueAtTime(.0001, n); g.gain.exponentialRampToValueAtTime(.16, n + .012); g.gain.exponentialRampToValueAtTime(.0001, n + .28);
    o.connect(g).connect(A.destination); o.start(n); o.stop(n + .3);
  } catch (e) { /* no audio */ }
}
const complete = run(async (id, li) => {
  const x = byId.get(id); if (!x) return;
  if (li) li.classList.add("closing");
  sound(); navigator.vibrate && navigator.vibrate(8);
  await sleep(330);
  const rid = OUTBOX && CocheOutbox.newRid();
  if (OUTBOX && CocheOutbox.isTemp(id)) return closeOffline(id, rid);   // added offline, not on the server yet
  let res;
  try { res = await api("POST", `/api/coche/tasks/${id}/close`, undefined, rid); }
  catch (e) { if (e.offline && OUTBOX) return closeOffline(id, rid); if (li) li.classList.remove("closing"); throw e; }
  S.stats.today = (S.stats.today || 0) + 1; S.stats.week = (S.stats.week || 0) + 1; ACTIVITY = null;
  if (res.recurring) {
    put(res.task); render();
    toast(t("Done! Next: {0}", dueInfo(res.task).text), run(async () => { put(await api("POST", `/api/v1/tasks/${id}/reopen`, { previous_date: res.previous_date })); S.stats.today--; render(); }));
  } else {
    const ids = res.closed || [id]; dropTree(id); render();
    if (S.stats.today === S.stats.daily_goal) setTimeout(() => toast("🎉 " + t("Daily goal reached! {0} tasks today.", S.stats.today)), 400);
    else toast(t("Task completed"), run(async () => { for (const i of ids.slice().reverse()) put(await api("POST", `/api/v1/tasks/${i}/reopen`)); S.stats.today--; render(); }));
  }
  setTimeout(() => api("GET", "/api/coche/stats").then(s => { S.stats = s; if (R.view === "today" || R.view === "completed") renderView(); }).catch(() => {}), 800);
});
function closeOffline(id, rid) {
  const op = queueOffline({ rid, kind: "close", task_id: id });
  if (DETAIL === id) closeDetail();
  render();
  toast(t("Completed offline, sent when back online"), () => { if (OUTBOX.cancel(op.rid)) rebuild(); banner(); });
}
const removeTask = run(async id => {
  const x = byId.get(id); if (!x) return;
  const n = countDeep(id);
  if (n && !(await confirmBox(t("Delete task?"), t("“{0}” and its {1} subtasks will be deleted.", x.content, n), t("Delete")))) return;
  await api("DELETE", `/api/v1/tasks/${id}`); dropTree(id); if (DETAIL === id) closeDetail(); render();
  toast(t("Task deleted"), run(async () => { await api("POST", `/api/coche/tasks/${id}/restore`); await load(true); render(); }));
});
const duplicate = run(async id => {
  const x = byId.get(id);
  const copy = await api("POST", "/api/v1/tasks", { content: x.content, description: x.description, project_id: x.project_id, section_id: x.section_id, parent_id: x.parent_id, priority: x.priority, labels: x.labels, due_date: dueDay(x) || undefined, due_time: dueTime(x) || undefined, rule: x.rule, deadline_date: x.deadline ? x.deadline.date : undefined, child_order: x.child_order + 0.5 });
  put(copy); render(); toast(t("Task duplicated"));
});
function scheduleTask(anchor, id) {
  const x = byId.get(id);
  datePicker(anchor, x.due ? { date: dueDay(x), time: dueTime(x), recurring: x.due.is_recurring, string: x.due.string } : null, run(async spec => {
    const body = { ...spec }; delete body.label;
    if (body.due_date && x.due && dueTime(x) && !body.due_time) body.due_time = dueTime(x);
    await updateTask(id, body); toast(t("Scheduled: {0}", byId.get(id) && byId.get(id).due ? dueInfo(byId.get(id)).text : t("No date")));
  }));
}
function taskMenu(anchor, id) {
  const x = byId.get(id);
  menu(anchor, [
    { icon: ic("edit", "s"), label: t("Open"), run: () => openDetail(id) },
    { icon: ic("cal", "s"), label: t("Schedule…"), run: () => scheduleTask(anchor, id) },
    { icon: ic("flag", "s"), label: t("Priority…"), run: () => priorityPicker(anchor, x.priority, p => updateTask(id, { priority: p })) },
    { icon: ic("arrow", "s"), label: t("Move to…"), run: () => projectPicker(anchor, x, run(async d => { put(await api("POST", `/api/v1/tasks/${id}/move`, d.section_id ? { section_id: d.section_id } : { project_id: d.project_id })); await load(true); })) },
    { icon: ic("copy", "s"), label: t("Duplicate"), run: () => duplicate(id) },
    "-",
    { icon: ic("trash", "s"), label: t("Delete"), danger: true, run: () => removeTask(id) },
  ]);
}

/* ------------------------------------------------------------------ quick add */
const QA = { ctx: {}, manual: {}, parsed: null, seq: 0 };
function openQuick(ctx = {}) {
  closePop();
  const def = {};
  if (R.view === "project" || R.view === "inbox") def.project_id = R.view === "inbox" ? inbox().id : R.id;
  if (R.view === "today" && !ctx.project_id && !ctx.parent_id) def.due = todayS();
  if (R.view === "label") def.labels = [R.id];
  QA.ctx = { ...def, ...ctx };
  QA.manual = {
    project_id: QA.ctx.project_id || null, section_id: QA.ctx.section_id || null, parent_id: QA.ctx.parent_id || null,
    priority: null, labels: QA.ctx.labels || [], due: QA.ctx.due ? { due_date: QA.ctx.due } : null, reminders: [],
  };
  QA.parsed = null;
  $("#qa-input").value = ""; $("#qa-desc").value = ""; $("#qa-hl").innerHTML = "";
  renderQAChips();
  $("#quick").classList.add("open"); $("#quick-scrim").classList.add("open");
  setTimeout(() => $("#qa-input").focus(), 40);
}
function closeQuick() { $("#quick").classList.remove("open"); $("#quick-scrim").classList.remove("open"); $("#qa-input").blur(); }
function qaProject() {
  const p = QA.parsed && QA.parsed.project_id && QA.parsed.project ? QA.parsed.project_id : QA.manual.project_id;
  return projById.get(p) || inbox();
}
function renderQAChips() {
  const P = QA.parsed || {}, M = QA.manual;
  const due = P.due && P.due.date ? { label: dayLabel(P.due.date) + (P.due.time ? " " + hm(P.due.time) : "") + (P.due.is_recurring ? " ↻" : ""), parsed: true } : M.due ? { label: dateSpecLabel(M.due) } : null;
  const prio = P.priority > 1 ? P.priority : M.priority || 1;
  const labels = [...new Set([...(P.labels || []), ...M.labels])];
  const p = qaProject(), sid = (P.section && P.section_id) || M.section_id, sec = secById.get(sid);
  const parent = M.parent_id && byId.get(M.parent_id);
  const rem = (P.reminders || []).length + M.reminders.filter(r => (r.minutes_before ?? 0) !== -1).length;
  $("#qa-chips").innerHTML = `
    <button class="chip${due ? " set" : ""}" data-a="qa-date" style="${due ? "color:var(--due-today)" : ""}">${ic("cal", "s")}${esc(due ? due.label : t("Date"))}${due && !due.parsed ? `<span class="x" data-a="qa-nodate">${ic("x", "xs")}</span>` : ""}</button>
    ${P.deadline ? `<span class="chip set" style="color:var(--due-week)">${ic("target", "s")}${esc(dayLabel(P.deadline))}</span>` : ""}
    <button class="chip${prio > 1 ? " set" : ""}" data-a="qa-prio" style="${prio > 1 ? `color:var(--${PRIO[prio]})` : ""}">${ic("flag", "s")}${prio > 1 ? "P" + (5 - prio) : t("Priority")}</button>
    <button class="chip${labels.length ? " set" : ""}" data-a="qa-labels">${ic("tag", "s")}${labels.length ? esc(labels.join(", ")) : t("Labels")}</button>
    <button class="chip${rem ? " set" : ""}" data-a="qa-rem">${ic("bell", "s")}${rem ? plural(rem, "{0} reminder", "{0} reminders") : t("Reminders")}</button>`;
  $("#qa-project").innerHTML = parent ? `${ic("sub", "s")}${esc(t("Subtask of “{0}”", parent.content.slice(0, 40)))}` : `${p.is_inbox_project ? `<span style="color:var(--p3)">${ic("inbox", "s")}</span>` : `<i class="dot" style="background:${col(p.color)}"></i>`}${esc(projName(p))}${sec ? " / " + esc(sec.name) : ""}${ic("down", "xs")}`;
  $("#qa-submit").disabled = !$("#qa-input").value.trim();
}
function highlight(text, marks) {
  let out = "", pos = 0;
  for (const m of marks || []) {
    const i = text.indexOf(m.text, pos); if (i < 0) continue;
    out += esc(text.slice(pos, i)) + `<mark class="${m.kind}">${esc(m.text)}</mark>`; pos = i + m.text.length;
  }
  return out + esc(text.slice(pos)) + "\u200b";
}
async function qaInput() {
  const inp = $("#qa-input"), v = inp.value;
  inp.style.height = "auto"; inp.style.height = inp.scrollHeight + "px";
  $("#qa-hl").innerHTML = highlight(v, QA.parsed ? QA.parsed.marks : []);
  renderQAChips();
  const my = ++QA.seq;
  if (!v.trim()) { QA.parsed = null; $("#qa-hl").innerHTML = ""; renderQAChips(); return; }
  await sleep(90); if (my !== QA.seq) return;
  const r = await api("POST", "/api/coche/parse", { text: v, project_id: QA.manual.project_id, lang: LANG }).catch(() => null);
  if (my !== QA.seq || !r) return;
  QA.parsed = r;
  $("#qa-hl").innerHTML = highlight(inp.value, r.marks);
  renderQAChips();
}
const qaSubmit = run(async () => {
  const text = $("#qa-input").value.trim(); if (!text) return;
  const M = QA.manual, P = QA.parsed || {};
  const body = { text, description: $("#qa-desc").value.trim(), project_id: M.project_id || undefined, section_id: M.section_id || undefined,
    parent_id: M.parent_id || undefined, priority: M.priority || undefined, labels: M.labels };
  if (M.due && !(P.due && P.due.date)) { if (M.due.due_string) body.due_string = M.due.due_string; else { body.due_date = M.due.due_date; body.due_time = M.due.due_time || undefined; } }
  $("#qa-submit").disabled = true;
  const rid = OUTBOX && CocheOutbox.newRid();
  let x;
  try { x = await api("POST", "/api/v1/tasks/quick", body, rid); }
  catch (e) {
    if (!e.offline || !OUTBOX) { $("#qa-submit").disabled = false; throw e; }
    // Offline: kept as typed (the server reads dates and #projects when it gets it), shown with ⏳.
    const op = queueOffline({ rid, kind: "add", body });
    for (const r of M.reminders) OUTBOX.push({ kind: "reminder", task_id: CocheOutbox.tempId(op), body: r });
    $("#qa-input").value = ""; $("#qa-desc").value = ""; $("#qa-hl").innerHTML = ""; QA.parsed = null; M.reminders = []; M.priority = null;
    $("#qa-input").style.height = "auto"; $("#qa-submit").disabled = false; $("#qa-input").focus();
    renderQAChips(); render(); banner();
    toast(t("Saved offline, sent when back online"));
    return;
  }
  for (const r of M.reminders) await api("POST", "/api/coche/reminders", { task_id: x.id, ...r });
  put(x);
  S.reminders = (await api("GET", "/api/coche/reminders")) || S.reminders;
  $("#qa-input").value = ""; $("#qa-desc").value = ""; $("#qa-hl").innerHTML = ""; QA.parsed = null; M.reminders = []; M.priority = null;
  $("#qa-input").style.height = "auto"; $("#qa-input").focus();
  renderQAChips(); render();
  const p = projById.get(x.project_id);
  toast(t("Added to {0}", projName(p)) + (x.due ? " · " + dueInfo(x).text : ""), () => openDetail(x.id), t("Open"));
});

/* ------------------------------------------------------------------ detail panel */
let DETAIL = null, COMMENTS = {};
function openDetail(id) {
  if (OUTBOX && CocheOutbox.isTemp(id)) { toast(t("Waiting to sync: you can edit it once it is on the server.")); return; }
  if (!byId.has(id)) { toast(t("This task is completed or was deleted.")); return; }
  const was = DETAIL; DETAIL = id; SEL = id;
  document.body.classList.add("detail-open");
  if (!location.hash.startsWith("#task=")) history.pushState({ detail: id }, "", location.pathname + location.search + "#task=" + id);
  else if (was !== id) history.replaceState({ detail: id }, "", location.pathname + location.search + "#task=" + id);
  renderDetail(); loadComments(id);
  $$(".task.sel").forEach(e => e.classList.toggle("sel", e.dataset.id === id));
}
function closeDetail(fromHistory) {
  if (!DETAIL) return;
  flushDetail();
  DETAIL = null; SEL = null; document.body.classList.remove("detail-open");
  $$(".task.sel").forEach(e => e.classList.remove("sel"));
  if (!fromHistory && location.hash.startsWith("#task=")) history.back();
}
async function loadComments(id) {
  try { COMMENTS[id] = (await api("GET", `/api/v1/comments?task_id=${id}`)).results; if (DETAIL === id) renderComments(); } catch (e) { /* ignore */ }
}
function renderComments() {
  const el = $("#d-comments"); if (!el || !DETAIL) return;
  const list = COMMENTS[DETAIL] || [];
  el.innerHTML = list.map(c => `<div class="comment"><div class="when"><span>${esc(new Date(c.posted_at).toLocaleString(locale(), { dateStyle: "short", timeStyle: "short" }))}</span><button class="ib" style="width:24px;height:24px" data-a="c-del" data-id="${c.id}">${ic("x", "xs")}</button></div><div class="txt">${md(c.content)}</div></div>`).join("");
}
function flushDetail() {
  if (!DETAIL || !byId.has(DETAIL)) return;
  const x = byId.get(DETAIL), title = $("#d-title"), desc = $("#d-desc");
  const body = {};
  if (title && title.value.trim() && title.value.trim() !== x.content) body.content = title.value.trim();
  if (desc && desc.value !== x.description) body.description = desc.value;
  if (Object.keys(body).length) run(updateTask)(DETAIL, body);
}
function grow(el) { if (el) { el.style.height = "auto"; el.style.height = el.scrollHeight + "px"; } }
function renderDetail() {
  const x = byId.get(DETAIL); if (!x) return closeDetail();
  const p = projById.get(x.project_id), s = secById.get(x.section_id), parent = x.parent_id && byId.get(x.parent_id);
  const di = dueInfo(x), rem = remOf(x.id);
  const sub = kids.get(x.id) || [];
  const focused = document.activeElement && document.activeElement.closest && document.activeElement.closest("#detail") && document.activeElement.id;
  $("#detail").innerHTML = `
    <div class="d-head"><button class="select-chip grow" data-a="d-move">${p && p.is_inbox_project ? `<span style="color:var(--p3)">${ic("inbox", "s")}</span>` : `<i class="dot" style="background:${col(p && p.color)}"></i>`}${esc(projName(p))}${s ? " / " + esc(s.name) : ""}</button>
      <button class="ib" data-a="d-more" title="${esc(t("More"))}">${ic("more")}</button><button class="ib" data-a="d-close" title="${esc(t("Close"))} (Esc)">${ic("x")}</button></div>
    <div class="d-body">
      ${parent ? `<button class="select-chip" data-a="open-id" data-id="${parent.id}" style="margin:-6px 0 6px -8px">${ic("sub", "s")}${esc(parent.content)}</button>` : ""}
      <div class="d-main"><button class="check ${PRIO[x.priority]}" data-a="d-check">${ic("check")}</button>
        <div style="flex:1;min-width:0"><textarea id="d-title" class="d-title" rows="1" enterkeyhint="done">${esc(x.content)}</textarea>
        <textarea id="d-desc" class="d-desc" rows="1" placeholder="${esc(t("Description"))}">${esc(x.description)}</textarea></div></div>
      <div class="props">
        <div class="prop"><span class="k">${ic("cal", "s")}${t("Date")}</span><span class="v"><button class="val ${di ? di.cls : "muted"}" data-a="d-date">${di ? esc(di.text) : t("No date")}${x.due && x.due.is_recurring ? ` ${ic("repeat", "xs")} <span class="muted" style="font-size:12.5px">${esc(x.due.string)}</span>` : ""}</button></span></div>
        <div class="prop"><span class="k">${ic("target", "s")}${t("Deadline")}</span><span class="v"><button class="val${x.deadline ? " dl" : " muted"}" data-a="d-deadline">${x.deadline ? esc(cap(wdShort(D(x.deadline.date))) + " " + dmy(D(x.deadline.date))) + (dayDiff(x.deadline.date) >= 0 ? ` <span class="muted" style="font-size:12.5px">· ${esc(t("in {0} d", dayDiff(x.deadline.date)))}</span>` : "") : t("Add")}</button>${x.deadline ? `<button class="ib" data-a="d-nodeadline" style="width:28px;height:28px">${ic("x", "xs")}</button>` : ""}</span></div>
        <div class="prop"><span class="k">${ic("flag", "s")}${t("Priority")}</span><span class="v"><button class="val" data-a="d-prio" style="color:var(--${PRIO[x.priority]})">${ic("flag", "s").replace("<path", '<path fill="' + (x.priority > 1 ? "currentColor" : "none") + '"')} P${5 - x.priority}</button></span></div>
        <div class="prop"><span class="k">${ic("tag", "s")}${t("Labels")}</span><span class="v">${x.labels.map(l => `<span class="tag">${esc(l)}</span>`).join("")}<button class="val muted" data-a="d-labels">${x.labels.length ? ic("edit", "xs") : t("Add")}</button></span></div>
        <div class="prop"><span class="k">${ic("bell", "s")}${t("Reminders")}</span><span class="v">${autoOn(x) ? `<span class="tag" title="${esc(t("Automatic reminder (Settings)"))}">${esc(remLabel({ minutes_before: S.settings.auto_reminder }))} · auto</span>` : ""}${rem.map(r => `<span class="tag">${esc(remLabel(r))}<button data-a="rem-del" data-id="${r.id}" style="display:grid">${ic("x", "xs")}</button></span>`).join("")}<button class="val muted" data-a="d-rem">${rem.length || autoOn(x) ? ic("plus", "xs") + " " + t("Add") : t("Add")}</button></span></div>
        <div class="prop"><span class="k">${ic("clock", "s")}${t("Duration")}</span><span class="v"><select id="d-duration" style="border:0;background:transparent;padding:4px 0">${[0, 15, 30, 45, 60, 90, 120, 180, 240].map(m => `<option value="${m}"${(x.duration ? x.duration.amount : 0) === m ? " selected" : ""}>${m ? fmtDur(m) : "—"}</option>`).join("")}${x.duration && ![15, 30, 45, 60, 90, 120, 180, 240].includes(x.duration.amount) ? `<option selected value="${x.duration.amount}">${fmtDur(x.duration.amount)}</option>` : ""}</select></span></div>
      </div>
      <div class="d-sec"><h4>${ic("sub", "s")}${t("Subtasks")} ${sub.length ? `<span class="muted">${sub.length}</span>` : ""}</h4>
        <ul class="list" data-drop="sub" data-parent="${x.id}" data-project="${x.project_id}">${sub.map(k => taskHTML(k, { drag: true })).join("")}</ul>
        <div class="inline-add">${ic("plus", "s")}<input id="d-subadd" placeholder="${esc(t("Add subtask (Enter)"))}" enterkeyhint="send" autocomplete="off"></div></div>
      <div class="d-sec"><h4>${ic("comment", "s")}${t("Comments")}</h4><div id="d-comments"></div>
        <div class="c-form"><textarea id="d-comment" rows="1" placeholder="${esc(t("Write a comment"))}"></textarea><button class="btn primary" data-a="c-add">${t("Send")}</button></div></div>
      <div class="d-foot">${t("Added {0}", esc(new Date(x.added_at).toLocaleString(locale(), { dateStyle: "medium", timeStyle: "short" })))}</div>
    </div>`;
  grow($("#d-title")); grow($("#d-desc")); renderComments();
  if (focused && $("#" + focused)) $("#" + focused).focus();
  const title = $("#d-title");
  title.addEventListener("keydown", e => { if (e.key === "Enter") { e.preventDefault(); title.blur(); } });
  title.addEventListener("input", () => grow(title)); title.addEventListener("blur", flushDetail);
  $("#d-desc").addEventListener("input", e => grow(e.target)); $("#d-desc").addEventListener("blur", flushDetail);
  $("#d-duration").addEventListener("change", e => run(updateTask)(x.id, { duration: +e.target.value || null }));
  $("#d-subadd").addEventListener("keydown", run(async e => {
    if (e.key !== "Enter" || !e.target.value.trim()) return;
    e.preventDefault(); const v = e.target.value.trim(); e.target.value = "";
    put(await api("POST", "/api/v1/tasks/quick", { text: v, parent_id: x.id })); render();
    setTimeout(() => $("#d-subadd") && $("#d-subadd").focus(), 20);
  }));
}

/* ------------------------------------------------------------------ click actions */
const A = {
  open: (el, e) => { if (e.target.closest("a[data-ext]")) return "pass"; if (Date.now() < noClickUntil) return; openDetail(el.closest(".task").dataset.id); },
  "open-id": el => openDetail(el.dataset.id),
  check: el => { if (Date.now() < noClickUntil) return; const li = el.closest(".task"); complete(li.dataset.id, li); },
  uncheck: run(async el => { const id = el.closest(".task").dataset.id; put(await api("POST", `/api/v1/tasks/${id}/reopen`)); Object.keys(DONE_CACHE).forEach(k => DONE_CACHE[k] = DONE_CACHE[k].filter(x => x.id !== id)); render(); }),
  "undo-done": run(async el => { put(await api("POST", `/api/v1/tasks/${el.dataset.id}/reopen`)); ACTIVITY = null; S.stats = await api("GET", "/api/coche/stats"); render(); toast(t("Task restored")); }),
  twisty: el => { const id = el.closest(".task").dataset.id; collapsed.has(id) ? collapsed.delete(id) : collapsed.add(id); localStorage.setItem("coche-collapsed", JSON.stringify([...collapsed])); const x = byId.get(id); if (x && x.is_collapsed) run(updateTask)(id, { is_collapsed: false }); else renderView(); },
  group: el => el.closest(".group").classList.toggle("closed"),
  quick: el => openQuick({ project_id: el.dataset.project || undefined, section_id: el.dataset.section || undefined, due: el.dataset.due, labels: el.dataset.labels ? [el.dataset.labels] : undefined }),
  "row-date": (el) => scheduleTask(el, el.closest(".task").dataset.id),
  "row-more": el => taskMenu(el, el.closest(".task").dataset.id),
  search: () => go("/search"),
  menu: () => document.body.classList.toggle("nav-open"),
  "nav-collapse": () => document.body.classList.toggle("nav-collapsed"),
  resched: el => datePicker(el, null, run(async spec => {
    const ids = S.tasks.filter(x => dueDay(x) && dueDay(x) < todayS()).map(x => x.id);
    const day = spec.due_date || todayS();
    const r = await api("POST", "/api/coche/reschedule", { ids, date: day }); r.tasks.forEach(put); render();
    toast(t("{0} tasks moved to {1}", ids.length, dayLabel(day)));
  })),
  "up-prev": () => { UP = addDays(UP, -7); renderView(false); }, "up-next": () => { UP = addDays(UP, 7); renderView(false); },
  "up-today": () => { UP = weekStart(todayD()); renderView(false); },
  "up-jump": el => { const g = $("#day-" + el.dataset.day); if (g) g.scrollIntoView({ behavior: "smooth", block: "start" }); },
  "proj-view": run(async () => { const p = projById.get(R.view === "inbox" ? inbox().id : R.id); const x = await api("POST", `/api/v1/projects/${p.id}`, { view_style: p.view_style === "board" ? "list" : "board" }); Object.assign(p, x); renderView(); }),
  "proj-done": run(async () => { const pid = R.view === "inbox" ? inbox().id : R.id; if (DONE_CACHE[pid]) { delete DONE_CACHE[pid]; return renderView(); } const since = new Date(Date.now() - 90 * 864e5).toISOString(); DONE_CACHE[pid] = (await api("GET", `/api/v1/tasks/completed/by_completion_date?project_id=${pid}&limit=200&since=${encodeURIComponent(since)}`)).items; renderView(); }),
  "proj-add": () => editProject(null),
  "proj-more": (el, e) => { e.stopPropagation(); projectMenu(el, el.dataset.id || (R.view === "inbox" ? inbox().id : R.id)); },
  "proj-unarchive": run(async el => { await api("POST", `/api/v1/projects/${el.dataset.id}/unarchive`); await load(true); toast(t("Project restored")); }),
  "sec-add": run(async el => { const r = await formBox(t("Add section"), [{ name: "name", label: t("Name"), required: true }], t("Add")); if (!r || !r.name) return; S.sections.push(await api("POST", "/api/v1/sections", { name: r.name, project_id: el.dataset.project, order: el.dataset.order ? +el.dataset.order - 0.5 : undefined })); await load(true); }),
  "sec-toggle": run(async el => { const s = secById.get(el.dataset.id); s.is_collapsed = !s.is_collapsed; renderView(); await api("POST", `/api/v1/sections/${s.id}`, { is_collapsed: s.is_collapsed }); }),
  "sec-more": (el) => sectionMenu(el, el.dataset.id),
  "filter-add": () => editFilter(null), "filter-edit": el => editFilter(el.dataset.id),
  "label-add": () => editLabel(null), "label-edit": el => editLabel(el.dataset.id),
  "qa-date": el => { if (QA.parsed && QA.parsed.due && QA.parsed.due.date) return; datePicker(el, QA.manual.due && QA.manual.due.due_date ? { date: QA.manual.due.due_date, time: QA.manual.due.due_time } : null, spec => { QA.manual.due = spec.due_string === "no date" ? null : spec; renderQAChips(); $("#qa-input").focus(); }); },
  "qa-nodate": (el, e) => { e.stopPropagation(); QA.manual.due = null; renderQAChips(); },
  "qa-prio": el => priorityPicker(el, QA.manual.priority || 1, p => { QA.manual.priority = p; renderQAChips(); $("#qa-input").focus(); }),
  "qa-labels": el => labelPicker(el, QA.manual.labels, ls => { QA.manual.labels = ls; renderQAChips(); }),
  "qa-rem": el => { const P = QA.parsed || {}, due = P.due && P.due.date ? { day: P.due.date, time: P.due.time } : QA.manual.due && QA.manual.due.due_date ? { day: QA.manual.due.due_date, time: QA.manual.due.due_time } : null;
    const key = r => JSON.stringify([r.minutes_before ?? r.minute_offset ?? null, r.time || null, r.at || null]);
    reminderPicker(el, { due, list: () => QA.manual.reminders, onclose: renderQAChips,
      add: r => { QA.manual.reminders.push(r); }, remove: r => { QA.manual.reminders = QA.manual.reminders.filter(x => key(x) !== key(r)); } }); },
  "qa-project": el => projectPicker(el, { project_id: qaProject().id, section_id: QA.manual.section_id }, d => { QA.manual.project_id = d.project_id; QA.manual.section_id = d.section_id; QA.manual.parent_id = null; renderQAChips(); $("#qa-input").focus(); }),
  "qa-submit": () => qaSubmit(), "qa-close": () => closeQuick(),
  "d-close": () => closeDetail(), "d-check": () => { const id = DETAIL; closeDetail(); complete(id, $(`.task[data-id="${id}"]`)); },
  "d-date": el => scheduleTask(el, DETAIL),
  "d-nodeadline": () => run(updateTask)(DETAIL, { deadline_date: null }),
  "d-deadline": el => { const id = DETAIL, x = byId.get(id); datePicker(el, x.deadline ? { date: x.deadline.date } : null, spec => { if (spec.due_string === "no date") return run(updateTask)(id, { deadline_date: null }); if (spec.due_date) return run(updateTask)(id, { deadline_date: spec.due_date }); run(async () => { const r = await api("POST", "/api/coche/parse", { text: spec.due_string }); if (r.due && r.due.date) await updateTask(id, { deadline_date: r.due.date }); })(); }); },
  "d-prio": el => priorityPicker(el, byId.get(DETAIL).priority, p => run(updateTask)(DETAIL, { priority: p })),
  "d-labels": el => { const id = DETAIL; labelPicker(el, byId.get(id).labels, ls => { const x = byId.get(id); if (x && ls.join() !== x.labels.join()) run(async () => { await updateTask(id, { labels: ls }); S.labels = (await api("GET", "/api/v1/labels?limit=200")).results; render(); })(); }); },
  "d-rem": el => { const id = DETAIL, x = byId.get(id);
    reminderPicker(el, { due: dueDay(x) ? { day: dueDay(x), time: dueTime(x) } : null, onclose: () => { if (DETAIL === id) renderDetail(); renderView(); },
      list: () => S.reminders.filter(r => r.item_id === id),
      add: async r => { const n = await api("POST", "/api/coche/reminders", { task_id: id, ...r }); if (!S.reminders.some(y => y.id === n.id)) S.reminders.push(n); },
      remove: async r => { await api("DELETE", `/api/coche/reminders/${r.id}`); S.reminders = S.reminders.filter(y => y.id !== r.id); } }); },
  "rem-del": run(async el => { await api("DELETE", `/api/coche/reminders/${el.dataset.id}`); S.reminders = S.reminders.filter(r => r.id !== el.dataset.id); renderDetail(); renderView(); }),
  "d-move": el => { const x = byId.get(DETAIL); projectPicker(el, x, run(async d => { put(await api("POST", `/api/v1/tasks/${x.id}/move`, d.section_id ? { section_id: d.section_id } : { project_id: d.project_id })); await load(true); })); },
  "d-more": el => taskMenu(el, DETAIL),
  "c-add": run(async () => { const ta = $("#d-comment"); const v = ta.value.trim(); if (!v) return; const id = DETAIL; const c = await api("POST", "/api/v1/comments", { task_id: id, content: v }); (COMMENTS[id] = COMMENTS[id] || []).push(c); ta.value = ""; const x = byId.get(id); x.note_count = (x.note_count || 0) + 1; renderComments(); renderView(); }),
  "c-del": run(async el => { await api("DELETE", `/api/v1/comments/${el.dataset.id}`); COMMENTS[DETAIL] = (COMMENTS[DETAIL] || []).filter(c => c.id !== el.dataset.id); const x = byId.get(DETAIL); x.note_count = Math.max(0, (x.note_count || 1) - 1); renderComments(); renderView(); }),
  dayoff: run(async el => { const d = +el.dataset.day; const cur = new Set(S.settings.days_off || []); cur.has(d) ? cur.delete(d) : cur.add(d); S.settings = await api("POST", "/api/coche/settings", { days_off: [...cur].sort() }); renderView(); }),
  "notify-test": run(async () => { const r = await api("POST", "/api/coche/notify/test"); toast(r.ok ? t("Test sent through {0}", r.channels.join(", ")) : (r.error || t("Failed"))); }),
  copy: el => { const v = $("#" + el.dataset.target).textContent; navigator.clipboard ? navigator.clipboard.writeText(v).then(() => toast(t("Copied"))) : prompt("", v); },
  "import-todoist": run(async () => {
    const tok = $("#td-token").value.trim(); if (!tok) return toast(t("Paste your Todoist API token first."));
    $("#import-res").textContent = t("Importing… this can take a minute.");
    const r = await api("POST", "/api/coche/import/todoist", { token: tok }); $("#td-token").value = "";
    $("#import-res").textContent = t("Imported {0} projects, {1} sections, {2} labels, {3} tasks, {4} completed tasks, {5} comments.", r.projects, r.sections, r.labels, r.tasks, r.completed, r.comments) + (r.warnings.length ? " ⚠ " + r.warnings.join(" · ") : "");
    await load(true);
  }),
  export: run(async () => { const d = await api("GET", "/api/coche/export"); const a = document.createElement("a"); a.href = URL.createObjectURL(new Blob([JSON.stringify(d)], { type: "application/json" })); a.download = `coche-backup-${todayS()}.json`; a.click(); }),
  "token-add": run(async () => { const r = await formBox(t("New API token"), [{ name: "name", label: t("Name (e.g. the script that uses it)"), required: true }], t("Create")); if (!r || !r.name) return; const tok = await api("POST", "/api/coche/tokens", { name: r.name }); await modal(`<h3>${t("Your new token")}</h3><p class="hint">${t("Copy it now: it won't be shown again.")}</p><div class="code">${esc(tok.token)}</div><div class="acts"><button class="btn primary" data-r>${t("Done")}</button></div>`, (el, done) => el.addEventListener("click", e => e.target.closest("[data-r]") && done())); loadTokens(); }),
  "token-del": run(async el => { if (await confirmBox(t("Revoke token?"), t("Scripts using it will stop working."), t("Revoke"))) { await api("DELETE", `/api/coche/tokens/${el.dataset.id}`); loadTokens(); } }),
  shortcuts: () => showShortcuts(),
  logout: run(async () => {
    const n = OUTBOX ? OUTBOX.list().length : 0;
    if (n && !(await confirmBox(t("Log out?"), t("{0} offline changes are not sent yet and will be lost.", n), t("Log out")))) return;
    await api("POST", "/api/coche/logout", {});
    if (OUTBOX) OUTBOX.clear();
    try { localStorage.removeItem("coche-cache"); } catch (e) { /* ignore */ }
    try { if (window.caches) await caches.delete("coche-data"); } catch (e) { /* ignore */ }
    location.href = BASE + "/login";
  }),
};
let noClickUntil = 0;
document.addEventListener("click", e => {
  const nav = e.target.closest("a[data-nav]");
  if (nav && !e.metaKey && !e.ctrlKey && !e.target.closest("[data-a]")) { e.preventDefault(); go(nav.getAttribute("href").slice(BASE.length)); return; }
  const el = e.target.closest("[data-a]"); if (!el) return;
  const fn = A[el.dataset.a]; if (!fn) return;
  if (el.dataset.a === "open" && e.target.closest("a[data-ext]")) return;
  e.preventDefault(); fn(el, e);
});
document.addEventListener("change", run(async e => {
  const el = e.target;
  if (el.id === "restore-file" && el.files[0]) {
    if (!(await confirmBox(t("Restore this backup?"), t("Everything currently in Coche will be replaced."), t("Restore")))) return;
    await api("POST", "/api/coche/import", JSON.parse(await el.files[0].text())); await load(); toast(t("Backup restored"));
    return;
  }
  if (!el.dataset.set) return;
  let v = el.type === "checkbox" ? el.checked : el.value;
  if (el.dataset.num) v = v === "" && el.dataset.null !== undefined ? null : +v;
  S.settings = await api("POST", "/api/coche/settings", { [el.dataset.set]: v });
  applySettings(); render(); toast(t("Saved"));
}));
document.addEventListener("input", e => {
  if (e.target.id === "search-input") { const q = e.target.value; history.replaceState({}, "", BASE + "/search" + (q ? "?q=" + encodeURIComponent(q) : "")); R.q = q; clearTimeout(A._s); A._s = setTimeout(() => renderView(), 120); }
});

/* ------------------------------------------------------------------ project / section / label / filter editors */
async function editProject(id) {
  const p = id ? projById.get(id) : null;
  const parents = [{ value: "", label: t("No parent") }, ...S.projects.filter(x => !x.is_inbox_project && x.id !== id).map(x => ({ value: x.id, label: x.name }))];
  const r = await formBox(p ? t("Edit project") : t("Add project"), [
    { name: "name", label: t("Name"), value: p ? p.name : "", required: true },
    { name: "color", label: t("Colour"), type: "color", value: p ? p.color : "charcoal" },
    { name: "parent_id", label: t("Parent project"), type: "select", value: p ? p.parent_id || "" : "", options: parents },
    { name: "view_style", label: t("Layout"), type: "select", value: p ? p.view_style : "list", options: [{ value: "list", label: t("List") }, { value: "board", label: t("Board") }] },
    { name: "is_favorite", label: t("Add to favorites"), type: "switch", value: p && p.is_favorite },
    { name: "description", label: t("Description"), type: "textarea", value: p ? p.description : "" },
  ], p ? t("Save") : t("Add"));
  if (!r || !r.name) return;
  r.parent_id = r.parent_id || null;
  try {
    const x = p ? await api("POST", `/api/v1/projects/${id}`, r) : await api("POST", "/api/v1/projects", r);
    await load(true); if (!p) go("/project/" + x.id);
  } catch (e) { toast(e.message); }
}
function projectMenu(anchor, id) {
  const p = projById.get(id); if (!p) return;
  const items = [];
  if (!p.is_inbox_project) items.push({ icon: ic("edit", "s"), label: t("Edit"), run: () => editProject(id) }, { icon: ic("star", "s"), label: p.is_favorite ? t("Remove from favorites") : t("Add to favorites"), run: async () => { await api("POST", `/api/v1/projects/${id}`, { is_favorite: !p.is_favorite }); await load(true); } });
  items.push({ icon: ic(p.view_style === "board" ? "list" : "board", "s"), label: p.view_style === "board" ? t("List view") : t("Board view"), run: async () => { await api("POST", `/api/v1/projects/${id}`, { view_style: p.view_style === "board" ? "list" : "board" }); await load(true); } });
  items.push({ icon: ic("plus", "s"), label: t("Add section"), run: () => A["sec-add"]({ dataset: { project: id } }) });
  if (!p.is_inbox_project) items.push("-", { icon: ic("archive", "s"), label: p.is_archived ? t("Unarchive") : t("Archive"), run: async () => { await api("POST", `/api/v1/projects/${id}/${p.is_archived ? "unarchive" : "archive"}`); await load(true); if (!p.is_archived) { go("/inbox"); toast(t("Project archived")); } } },
    { icon: ic("trash", "s"), label: t("Delete"), danger: true, run: async () => { const n = S.tasks.filter(x => x.project_id === id).length; if (await confirmBox(t("Delete project?"), t("“{0}” and its {1} tasks will be deleted. This can't be undone.", p.name, n), t("Delete"))) { await api("DELETE", `/api/v1/projects/${id}`); await load(true); go("/inbox"); } } });
  menu(anchor, items);
}
function sectionMenu(anchor, id) {
  const s = secById.get(id);
  menu(anchor, [
    { icon: ic("edit", "s"), label: t("Rename"), run: async () => { const r = await formBox(t("Rename section"), [{ name: "name", label: t("Name"), value: s.name, required: true }]); if (r && r.name) { await api("POST", `/api/v1/sections/${id}`, { name: r.name }); await load(true); } } },
    { icon: ic("plus", "s"), label: t("Add task"), run: () => openQuick({ project_id: s.project_id, section_id: id }) },
    { icon: ic("trash", "s"), label: t("Delete"), danger: true, run: async () => { const n = S.tasks.filter(x => x.section_id === id).length; if (await confirmBox(t("Delete section?"), t("“{0}” and its {1} tasks will be deleted.", s.name, n), t("Delete"))) { await api("DELETE", `/api/v1/sections/${id}`); await load(true); } } },
  ]);
}
async function editLabel(id) {
  const l = id ? S.labels.find(x => x.id === id) : null;
  const r = await formBox(l ? t("Edit label") : t("Add label"), [
    { name: "name", label: t("Name"), value: l ? l.name : "", required: true },
    { name: "color", label: t("Colour"), type: "color", value: l ? l.color : "charcoal" },
    { name: "is_favorite", label: t("Add to favorites"), type: "switch", value: l && l.is_favorite },
  ], l ? t("Save") : t("Add"), l ? t("Delete") : null);
  if (r === "extra") { if (await confirmBox(t("Delete label?"), t("It will be removed from every task."), t("Delete"))) { await api("DELETE", `/api/v1/labels/${id}`); await load(true); } return; }
  if (!r || !r.name) return;
  try { l ? await api("POST", `/api/v1/labels/${id}`, r) : await api("POST", "/api/v1/labels", r); await load(true); } catch (e) { toast(e.message); }
}
async function editFilter(id) {
  const f = id ? S.filters.find(x => x.id === id) : null;
  const r = await formBox(f ? t("Edit filter") : t("Add filter"), [
    { name: "name", label: t("Name"), value: f ? f.name : "", required: true },
    { name: "query", label: t("Query"), value: f ? f.query : "", required: true, placeholder: "today | overdue", hint: t("Examples: <code>p1 &amp; 7 days</code> · <code>#Work &amp; !@waiting</code> · <code>no date</code> · <code>search: invoice</code>") },
    { name: "color", label: t("Colour"), type: "color", value: f ? f.color : "charcoal" },
    { name: "is_favorite", label: t("Add to favorites"), type: "switch", value: f && f.is_favorite },
  ], f ? t("Save") : t("Add"), f ? t("Delete") : null);
  if (r === "extra") { await api("DELETE", `/api/coche/filters/${id}`); await load(true); if (R.view === "filter") go("/labels"); return; }
  if (!r || !r.name) return;
  try { const x = f ? await api("POST", `/api/coche/filters/${id}`, r) : await api("POST", "/api/coche/filters", r); delete FILTER_CACHE[x.id]; await load(true); go("/filter/" + x.id); } catch (e) { toast(e.message); }
}
function showShortcuts() {
  const rows = [["Q", t("Add a task")], ["/", t("Search")], ["G T", t("Go to Today")], ["G U", t("Go to Upcoming")], ["G I", t("Go to Inbox")], ["G C", t("Go to Completed")], ["G S", t("Go to Settings")], ["Esc", t("Close")], ["?", t("This help")]];
  const qa = [["#Project", t("project")], ["/Section", t("section")], ["@label", t("label")], ["p1…p4", t("priority")], ["{date}", t("deadline")], ["!30min", t("reminder")], [t("tomorrow 2pm"), t("date and time")], [t("every monday"), t("recurrence")]];
  modal(`<h3>${t("Keyboard shortcuts")}</h3><div class="shortcuts">${rows.map(([k, v]) => `<span>${k.split(" ").map(x => `<kbd>${esc(x)}</kbd>`).join(" ")}</span><span>${esc(v)}</span>`).join("")}</div><h3 style="margin-top:18px">${t("Quick Add")}</h3><div class="shortcuts">${qa.map(([k, v]) => `<code>${esc(k)}</code><span>${esc(v)}</span>`).join("")}</div><div class="acts"><button class="btn primary" data-r>${t("Done")}</button></div>`, (el, done) => el.addEventListener("click", e => e.target.closest("[data-r]") && done()));
}

/* ------------------------------------------------------------------ keyboard */
let gPending = 0;
document.addEventListener("keydown", e => {
  const typing = e.target.closest("input, textarea, select, [contenteditable]");
  if (e.key === "Escape") {
    if (POP) return closePop();
    if (MODAL) return MODAL.close();
    if ($("#quick").classList.contains("open")) return closeQuick();
    if (DETAIL) return closeDetail();
    if (document.body.classList.contains("nav-open")) return closeNav();
    return;
  }
  if (e.target.id === "qa-input" && e.key === "Enter" && !e.shiftKey) { e.preventDefault(); return qaSubmit(); }
  if (typing || e.metaKey || e.ctrlKey || e.altKey) return;
  const k = e.key.toLowerCase();
  if (Date.now() - gPending < 1200) {
    gPending = 0;
    const to = { t: "/today", u: "/upcoming", i: "/inbox", c: "/completed", s: "/settings", l: "/labels" }[k];
    if (to) { e.preventDefault(); go(to); }
    return;
  }
  if (k === "g") { gPending = Date.now(); return; }
  if (k === "q" || k === "a") { e.preventDefault(); openQuick(); }
  else if (k === "/" || k === "f") { e.preventDefault(); go("/search"); }
  else if (e.key === "?") { e.preventDefault(); showShortcuts(); }
  else if (k === "m") document.body.classList.toggle("nav-collapsed");
});
function closeNav() { document.body.classList.remove("nav-open"); }

/* ------------------------------------------------------------------ swipe (touch) & drag and drop */
let SW = null, DR = null, PD = null, pressTimer = null;
document.addEventListener("pointerdown", e => {
  if (e.button > 0) return;
  const handle = e.target.closest(".handle");
  if (handle) { e.preventDefault(); return startDrag(e, handle.closest(".task")); }
  const row = e.target.closest(".task > .row");
  if (!row || e.target.closest("button:not(.row), a, input")) return;
  if (e.pointerType === "mouse") { if (row.parentElement.parentElement && row.parentElement.parentElement.dataset.drop) PD = { li: row.parentElement, x0: e.clientX, y0: e.clientY }; return; }
  if (e.pointerType !== "touch") return;
  const li = row.parentElement;
  SW = { li, row, x0: e.clientX, y0: e.clientY, dx: 0, axis: null, id: e.pointerId };
  if (li.parentElement && li.parentElement.dataset.drop) pressTimer = setTimeout(() => { if (SW && !SW.axis) { const ev = SW; SW = null; startDrag({ clientX: ev.x0, clientY: ev.y0 }, li); } }, 460);
});
addEventListener("pointermove", e => {
  if (DR) return moveDrag(e);
  if (PD && Math.hypot(e.clientX - PD.x0, e.clientY - PD.y0) > 6) { const p = PD; PD = null; startDrag({ clientX: p.x0, clientY: p.y0 }, p.li); return moveDrag(e); }
  if (!SW || e.pointerId !== SW.id) return;
  const dx = e.clientX - SW.x0, dy = e.clientY - SW.y0;
  if (!SW.axis && Math.hypot(dx, dy) > 8) { SW.axis = Math.abs(dx) > Math.abs(dy) * 1.2 ? "x" : "y"; clearTimeout(pressTimer); }
  if (SW.axis !== "x") { if (SW.axis === "y") SW = null; return; }
  SW.dx = dx;
  if (!SW.bg) { SW.bg = document.createElement("div"); SW.li.prepend(SW.bg); SW.row.style.transition = "none"; }
  SW.bg.className = "swipe-bg " + (dx > 0 ? "right" : "left");
  SW.bg.innerHTML = dx > 0 ? `<span>${ic("check")} ${t("Complete")}</span>` : `<span>${t("Schedule")} ${ic("cal")}</span>`;
  SW.bg.style.opacity = Math.min(1, Math.abs(dx) / 80);
  SW.row.style.transform = `translateX(${dx}px)`;
});
addEventListener("pointerup", e => {
  clearTimeout(pressTimer); PD = null;
  if (DR) return endDrag(e);
  if (!SW) return;
  const s = SW; SW = null;
  if (s.axis !== "x") return;
  noClickUntil = Date.now() + 350;
  s.row.style.transition = "transform .2s";
  const id = s.li.dataset.id;
  if (s.dx > 90) { s.row.style.transform = `translateX(${innerWidth}px)`; setTimeout(() => complete(id, s.li), 120); }
  else if (s.dx < -90) { s.row.style.transform = ""; setTimeout(() => { s.bg && s.bg.remove(); scheduleTask(s.li, id); }, 150); }
  else { s.row.style.transform = ""; setTimeout(() => s.bg && s.bg.remove(), 200); }
});
addEventListener("pointercancel", () => { clearTimeout(pressTimer); if (SW) { SW.row.style.transform = ""; SW.bg && SW.bg.remove(); SW = null; } if (DR) endDrag(null, true); });
addEventListener("touchmove", e => { if (DR || (SW && SW.axis === "x")) e.preventDefault(); }, { passive: false });

function startDrag(e, li) {
  const list = li && li.parentElement;
  if (!list || !list.dataset.drop) return;
  const r = li.getBoundingClientRect();
  const ghost = li.cloneNode(true); ghost.classList.add("dragging-ghost");
  Object.assign(ghost.style, { width: r.width + "px", left: r.left + "px", top: r.top + "px" });
  const ph = document.createElement("li"); ph.className = "task placeholder"; ph.style.height = r.height + "px";
  li.after(ph); li.style.display = "none"; document.body.append(ghost);
  document.body.classList.add("dragging"); getSelection().removeAllRanges();
  DR = { li, ghost, ph, dy: e.clientY - r.top, dx: e.clientX - r.left, from: list, kind: list.dataset.drop, x: e.clientX, y: e.clientY };
  navigator.vibrate && navigator.vibrate(12);
  DR.scroll = setInterval(() => { const v = $("#view"), vr = v.getBoundingClientRect(); if (DR.y < vr.top + 60) v.scrollTop -= 12; else if (DR.y > vr.bottom - 60) v.scrollTop += 12; }, 16);
}
function moveDrag(e) {
  DR.x = e.clientX; DR.y = e.clientY;
  DR.ghost.style.left = (e.clientX - DR.dx) + "px"; DR.ghost.style.top = (e.clientY - DR.dy) + "px";
  const el = document.elementFromPoint(e.clientX, e.clientY); if (!el) return;
  $$(".drop-on").forEach(x => x.classList.remove("drop-on"));
  let list = el.closest("[data-drop]");
  if (!list || list.dataset.drop !== DR.kind && !(DR.kind === "section" && list.dataset.drop === "section")) {
    const g = el.closest(".group, .col"); list = g && g.querySelector(`[data-drop="${DR.kind}"]`);
  }
  if (!list || list.dataset.drop !== DR.kind || DR.li.contains(list)) return;
  if (DR.kind === "sub" && list.dataset.parent !== DR.from.dataset.parent) return;
  const over = el.closest(".task:not(.placeholder)");
  if (over && over.parentElement === list && over !== DR.li) {
    const r = over.getBoundingClientRect();
    (e.clientY < r.top + r.height / 2) ? over.before(DR.ph) : over.after(DR.ph);
  } else if (!over || over.parentElement !== list) {
    if (DR.ph.parentElement !== list) list.append(DR.ph);
  }
  if (DR.ph.parentElement !== DR.from) list.classList.add("drop-on");
}
const endDrag = run(async (e, cancel) => {
  const d = DR; DR = null; clearInterval(d.scroll); document.body.classList.remove("dragging");
  $$(".drop-on").forEach(x => x.classList.remove("drop-on"));
  d.ghost.remove();
  const list = d.ph.parentElement;
  if (cancel || !list) { d.ph.remove(); d.li.style.display = ""; return; }
  d.ph.replaceWith(d.li); d.li.style.display = "";
  noClickUntil = Date.now() + 300;
  const id = d.li.dataset.id, x = byId.get(id);
  if (d.kind === "day") {
    const day = list.dataset.day;
    if (day && day !== dueDay(x)) { await updateTask(id, { due_date: day, due_time: dueTime(x) }); toast(t("Moved to {0}", dayLabel(day))); }
    return;
  }
  const ids = [...list.children].filter(c => c.classList.contains("task")).map(c => c.dataset.id);
  const body = { ids, project_id: list.dataset.project };
  if (d.kind === "section") { body.section_id = list.dataset.section || null; body.parent_id = null; }
  else { body.parent_id = list.dataset.parent; body.section_id = x.section_id; }
  const r = await api("POST", "/api/coche/reorder", body);
  r.tasks.forEach(put); await load(true);
});

/* ------------------------------------------------------------------ upcoming swipe between weeks */
let wk = null;
document.addEventListener("touchstart", e => { const s = e.target.closest("#weekstrip"); wk = s ? { x: e.touches[0].clientX, y: e.touches[0].clientY } : null; }, { passive: true });
document.addEventListener("touchend", e => {
  if (!wk) return; const dx = e.changedTouches[0].clientX - wk.x, dy = e.changedTouches[0].clientY - wk.y; wk = null;
  if (Math.abs(dx) > 60 && Math.abs(dx) > Math.abs(dy) * 1.5) { if (dx < 0) A["up-next"](); else if (UP > weekStart(todayD())) A["up-prev"](); }
});

/* ------------------------------------------------------------------ boot */
function shell() {
  document.body.insertAdjacentHTML("afterbegin", `
  <div id="c-offline" class="offline" hidden>${t("Offline: showing your last synced tasks")}</div>
  <div id="app">
    <aside id="sidebar" aria-label="${esc(t("Navigation"))}"></aside><div id="scrim" data-a="menu"></div>
    <main id="main"><header id="topbar"><button class="ib mob-only" data-a="menu" aria-label="${esc(t("Menu"))}">${ic("menu")}</button><button class="ib desk-collapsed" data-a="nav-collapse" aria-label="${esc(t("Show sidebar"))}">${ic("sidebar")}</button><div class="title"></div><button class="ib" data-a="search" aria-label="${esc(t("Search"))}">${ic("search")}</button></header><section id="view"><div class="loading"><div class="spin"></div></div></section></main>
  </div>
  <button id="fab" data-a="quick" aria-label="${esc(t("Add task"))}">${ic("plus")}</button>
  <div id="quick-scrim" class="sheet-scrim" data-a="qa-close"></div>
  <div id="quick" class="sheet" role="dialog" aria-label="${esc(t("Quick Add"))}">
    <div class="qa-field"><div id="qa-hl" class="qa-hl" aria-hidden="true"></div><textarea id="qa-input" class="qa-input" rows="1" placeholder="${esc(t("e.g. Pay rent every 5th #Home p1"))}" enterkeyhint="send" autocomplete="off" autocapitalize="sentences"></textarea></div>
    <textarea id="qa-desc" class="qa-desc" rows="1" placeholder="${esc(t("Description"))}"></textarea>
    <div class="chips" id="qa-chips"></div>
    <div class="sheet-foot"><button class="select-chip grow" id="qa-project" data-a="qa-project"></button><button class="btn ghost" data-a="qa-close">${t("Cancel")}</button><button class="btn primary" id="qa-submit" data-a="qa-submit">${t("Add task")}</button></div>
  </div>
  <aside id="detail" aria-label="${esc(t("Task"))}"></aside>
  <div id="toast" role="status" aria-live="polite"></div>`);
  $("#qa-input").addEventListener("input", qaInput);
  $("#qa-desc").addEventListener("input", e => grow(e.target));
  $("#view").addEventListener("scroll", () => document.body.classList.toggle("scrolled", $("#view").scrollTop > 30), { passive: true });
}
const style = document.createElement("style");
style.textContent = `@media (min-width:900px){.mob-only{display:none}body:not(.nav-collapsed) .desk-collapsed{display:none}}@media (max-width:899px){.desk-only,.desk-collapsed{display:none}}`;
document.head.append(style);

function boot() {
  try { const c = JSON.parse(localStorage.getItem("coche-cache") || "null"); if (c) { Object.assign(S, c); reindex(); applySettings(); } } catch (e) { /* bad cache */ }
  overlay();
  shell(); banner();
  addEventListener("online", () => { load(true); });
  R = parseRoute();
  if (S.tasks.length || S.projects.length) render();
  load().then(() => {
    if (new URLSearchParams(location.search).get("add")) openQuick();
    if (location.hash.startsWith("#task=")) openDetail(location.hash.slice(6));
  });
  setInterval(() => { if (!document.hidden && !$("#quick").classList.contains("open") && !(document.activeElement && document.activeElement.closest("#detail"))) load(true); }, 60000);
  document.addEventListener("visibilitychange", () => { if (!document.hidden) load(true); });
  let lastDay = todayS(); setInterval(() => { if (todayS() !== lastDay) { lastDay = todayS(); render(); } }, 30000);
  if (BOOT.sw && "serviceWorker" in navigator && window.isSecureContext) navigator.serviceWorker.register(BASE + "/sw.js", { scope: BASE + "/" }).catch(() => {});
  window.Coche = { S, load, go, openQuick, api };
}
boot();
})();
