"use strict";

/* ==========================================================================
   STUDENT ECOSYSTEM — CORE
   Helpers, state, API client, theme, router, overlays and command palette.
   ========================================================================== */

const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => Array.from(root.querySelectorAll(selector));

const VIEW_META = {
  overview: { title: "Overview", eyebrow: "Your daily companion" },
  campus: { title: "MIT-WPU Updates", eyebrow: "Campus intelligence" },
  opportunities: { title: "Hackathons & Events", eyebrow: "Opportunity radar" },
  news: { title: "AI News & Briefings", eyebrow: "Stay sharp" },
  mail: { title: "Mail Summarizer", eyebrow: "AI tool" },
  vault: { title: "Academic Vault", eyebrow: "Workspace" },
  tasks: { title: "Task Hub", eyebrow: "Workspace" },
  saved: { title: "Saved", eyebrow: "Your library" },
  settings: { title: "Settings", eyebrow: "Preferences" },
};

const TYPE_ICONS = {
  course: "grad",
  notes: "file",
  video: "video",
  practice: "bolt",
  tool: "tool",
  reference: "book",
  link: "link",
};

const state = {
  profile: {
    name: "MIT-WPU Student",
    branch: "Computer Science",
    year: "3rd Year",
    semester: "Semester 5",
    goal: "",
  },
  branches: [],
  college: {
    name: "MIT World Peace University",
    short_name: "MIT-WPU",
    city: "Pune, Maharashtra",
    url: "",
  },
  features: { ai: false, ai_mode: "heuristic", model: "", campus_live: false },
  stats: {},
  today: "",
  campus: [],
  campusCategories: {},
  campusStatus: null,
  campusUpdated: "",
  opportunities: [],
  oppTracks: [],
  news: [],
  newsMeta: null,
  summaries: [],
  tasks: [],
  taskCounts: { todo: 0, doing: 0, done: 0 },
  vault: [],
  vaultSubjects: [],
  vaultTypes: [],
  bookmarks: [],
  savedKeys: new Set(),
  briefing: null,
  currentSummary: null,
  loaded: {},
  filters: {
    campusCategory: "All",
    campusQuery: "",
    oppTrack: "All",
    oppMode: "All",
    oppDeadline: "",
    oppQuery: "",
    oppSaved: false,
    newsQuery: "",
    vaultQuery: "",
    vaultType: "All",
    vaultScope: "All",
    vaultSubject: "All",
    taskQuery: "",
    taskPriority: "All",
    savedType: "All",
  },
  paletteSelection: 0,
  paletteOptions: [],
};

/* --------------------------------------------------------------------------
   Escaping & formatting
   -------------------------------------------------------------------------- */

function esc(value) {
  return String(value === null || value === undefined ? "" : value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function safeUrl(value) {
  try {
    const url = new URL(String(value || ""), window.location.origin);
    if (!["http:", "https:"].includes(url.protocol)) return "";
    return url.href;
  } catch {
    return "";
  }
}

function icon(name, className = "") {
  return `<svg class="icon ${className}" aria-hidden="true"><use href="#i-${name}"/></svg>`;
}

function truncate(value, limit = 160) {
  const text = String(value || "").replace(/\s+/g, " ").trim();
  if (text.length <= limit) return text;
  const cut = text.slice(0, limit);
  const space = cut.lastIndexOf(" ");
  return `${cut.slice(0, space > limit * 0.6 ? space : limit).trim()}…`;
}

function plural(count, singular, pluralForm = `${singular}s`) {
  return `${count} ${count === 1 ? singular : pluralForm}`;
}

function parseDate(value) {
  if (!value) return null;
  const text = String(value);
  const candidate = /^\d{4}-\d{2}-\d{2}$/.test(text) ? `${text}T00:00:00` : text;
  const parsed = new Date(candidate);
  return Number.isNaN(parsed.getTime()) ? null : parsed;
}

function fmtDate(value, options = {}) {
  const date = parseDate(value);
  if (!date) return "Date TBD";
  const { year, ...rest } = options;
  return new Intl.DateTimeFormat("en-IN", {
    day: "numeric",
    month: "short",
    ...(year === false ? {} : { year: "numeric" }),
    ...rest,
  }).format(date);
}

function fmtDateTime(value) {
  const date = parseDate(value);
  if (!date) return "";
  return new Intl.DateTimeFormat("en-IN", {
    day: "numeric",
    month: "short",
    hour: "numeric",
    minute: "2-digit",
  }).format(date);
}

function timeAgo(value) {
  const date = parseDate(value);
  if (!date) return "";
  const diff = Date.now() - date.getTime();
  const minutes = Math.round(diff / 60000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.round(hours / 24);
  if (days < 7) return `${days}d ago`;
  return fmtDate(value, { year: false });
}

function todayISO() {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(
    now.getDate()
  ).padStart(2, "0")}`;
}

function daysUntil(value) {
  if (!value) return null;
  const date = parseDate(value);
  if (!date) return null;
  const start = new Date();
  start.setHours(0, 0, 0, 0);
  const target = new Date(date);
  target.setHours(0, 0, 0, 0);
  return Math.round((target - start) / 86400000);
}

function deadlineLabel(value) {
  if (!value) return { text: "Rolling", cls: "closed" };
  const days = daysUntil(value);
  if (days === null) return { text: "Date TBD", cls: "closed" };
  if (days < 0) return { text: "Closed", cls: "closed" };
  if (days === 0) return { text: "Due today", cls: "" };
  if (days === 1) return { text: "Due tomorrow", cls: "" };
  if (days <= 7) return { text: `${days} days left`, cls: "" };
  if (days <= 45) return { text: `In ${days} days`, cls: "closed" };
  return { text: fmtDate(value), cls: "closed" };
}

function urgencyClass(urgency) {
  const value = String(urgency || "normal").toLowerCase();
  if (["urgent", "high"].includes(value)) return "urgency-high";
  if (value === "medium") return "urgency-medium";
  return "urgency-normal";
}

function urgencyLabel(urgency) {
  const value = String(urgency || "normal").toLowerCase();
  return value.charAt(0).toUpperCase() + value.slice(1);
}

function priorityRank(priority) {
  return { urgent: 0, high: 1, medium: 2, low: 3 }[priority] || 4;
}

function debounce(fn, wait = 220) {
  let timer;
  return (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), wait);
  };
}

function nid(prefix = "item") {
  return `${prefix}-${Math.random().toString(36).slice(2, 9)}`;
}

/* --------------------------------------------------------------------------
   API client
   -------------------------------------------------------------------------- */

async function api(path, options = {}) {
  const { method = "GET", body, formData, timeout = 25000 } = options;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeout);
  const init = { method, signal: controller.signal, headers: { Accept: "application/json" } };
  if (body !== undefined) {
    init.headers["Content-Type"] = "application/json";
    init.body = JSON.stringify(body);
  }
  if (formData) init.body = formData;

  try {
    const response = await fetch(path, init);
    const text = await response.text();
    let data = {};
    try {
      data = text ? JSON.parse(text) : {};
    } catch {
      throw new Error("The server returned an unexpected response.");
    }
    if (!response.ok) {
      const error = new Error(data.error || `Request failed (${response.status}).`);
      error.status = response.status;
      error.data = data;
      throw error;
    }
    return data;
  } catch (error) {
    if (error.name === "AbortError") {
      throw new Error("That took too long. Check your connection and try again.");
    }
    throw error;
  } finally {
    clearTimeout(timer);
  }
}

/* --------------------------------------------------------------------------
   Toasts
   -------------------------------------------------------------------------- */

function toast(message, { type = "success", title = "" } = {}) {
  const stack = $("#toast-stack");
  if (!stack) return;
  const icons = { success: "check", error: "alert", info: "sparkles" };
  const node = document.createElement("div");
  node.className = `toast ${type}`;
  node.innerHTML = `
    <span class="toast-icon">${icon(icons[type] || "check")}</span>
    <div><strong>${esc(title || (type === "error" ? "Something went wrong" : "Done"))}</strong>
    <span>${esc(message)}</span></div>`;
  stack.appendChild(node);
  setTimeout(() => {
    node.classList.add("leaving");
    setTimeout(() => node.remove(), 260);
  }, 4200);
}

/* --------------------------------------------------------------------------
   Loading & empty states
   -------------------------------------------------------------------------- */

function skeletonCards(count = 4) {
  return Array.from(
    { length: count },
    () => `
      <div class="skeleton-stack" aria-hidden="true">
        <div style="display:flex;gap:8px">
          <div class="skeleton" style="height:22px;width:88px;border-radius:99px"></div>
          <div class="skeleton" style="height:22px;width:60px;border-radius:99px"></div>
        </div>
        <div class="skeleton skeleton-line med"></div>
        <div class="skeleton skeleton-line"></div>
        <div class="skeleton skeleton-line short"></div>
        <div class="skeleton" style="height:78px;border-radius:12px;margin-top:4px"></div>
      </div>`
  ).join("");
}

function skeletonPanel(message = "Loading…") {
  return `
    <div class="skeleton-stack" aria-hidden="true">
      <div class="skeleton skeleton-line short"></div>
      <div class="skeleton skeleton-line"></div>
      <div class="skeleton skeleton-line med"></div>
      <div class="skeleton" style="height:64px;border-radius:12px"></div>
      <span class="sr-only">${esc(message)}</span>
    </div>`;
}

function skeletonRows(count = 4) {
  return Array.from(
    { length: count },
    () => `
      <div style="display:flex;gap:10px;align-items:center;padding:8px 0">
        <div class="skeleton" style="width:36px;height:36px;border-radius:10px"></div>
        <div style="flex:1">
          <div class="skeleton skeleton-line med" style="margin-bottom:6px"></div>
          <div class="skeleton skeleton-line short" style="height:9px"></div>
        </div>
      </div>`
  ).join("");
}

function emptyState(iconName, title, text, action = "") {
  return `
    <div class="empty-state">
      <div class="empty-icon">${icon(iconName)}</div>
      <h3>${esc(title)}</h3>
      <p>${esc(text)}</p>
      ${action}
    </div>`;
}

/* --------------------------------------------------------------------------
   Saved items
   -------------------------------------------------------------------------- */

function saveKey(kind, id) {
  return `${kind}:${id}`;
}

function isSaved(kind, id) {
  return state.savedKeys.has(saveKey(kind, id));
}

function findItem(kind, id) {
  const pools = {
    campus: state.campus,
    news: state.news,
    opportunity: state.opportunities,
    summary: state.summaries,
    task: state.tasks,
    vault: state.vault,
  };
  return (pools[kind] || []).find((item) => String(item.id) === String(id)) || null;
}

function syncSavedKeys() {
  state.savedKeys = new Set(state.bookmarks.map((item) => item.item_key));
}

async function toggleSave(kind, id) {
  const item = findItem(kind, id);
  if (!item) return;
  const key = saveKey(kind, id);
  const url = item.link || item.url || "";
  const subtitle =
    kind === "opportunity"
      ? `${item.organizer || item.track || "Opportunity"}${item.deadline ? ` · ${fmtDate(item.deadline)}` : ""}`
      : kind === "news"
      ? `${item.source || "Briefing"}${item.published_at ? ` · ${timeAgo(item.published_at)}` : ""}`
      : `${item.category || "Campus"}${item.deadline ? ` · ${fmtDate(item.deadline)}` : ""}`;

  try {
    const result = await api("/api/bookmarks", {
      method: "POST",
      body: {
        item_key: key,
        type: kind,
        title: item.title || item.subject || "Saved item",
        subtitle,
        url,
        payload: { id, kind },
      },
    });
    if (result.saved) {
      state.savedKeys.add(key);
      toast("Saved to your library.", { title: "Bookmarked" });
    } else {
      state.savedKeys.delete(key);
      toast("Removed from your library.", { title: "Unsaved", type: "info" });
    }
    if (result.stats) {
      state.stats = result.stats;
      updateBadges();
    }
    const savedView = $("#view-saved");
    if (savedView && savedView.classList.contains("active")) await loadSaved(true);
    else await renderSaved(false);
    rerenderActiveView();
  } catch (error) {
    toast(error.message, { type: "error", title: "Could not update bookmark" });
  }
}

/* --------------------------------------------------------------------------
   Theme
   -------------------------------------------------------------------------- */

function currentTheme() {
  return document.documentElement.getAttribute("data-theme") || "light";
}

function applyTheme(theme, persist = true) {
  document.documentElement.setAttribute("data-theme", theme);
  if (persist) localStorage.setItem("se-theme", theme);
  const toggle = $("#theme-toggle");
  if (toggle) toggle.setAttribute("aria-pressed", String(theme === "dark"));
  const meta = document.querySelector('meta[name="theme-color"]');
  if (meta) meta.setAttribute("content", theme === "dark" ? "#070912" : "#5b4bff");
}

function initTheme() {
  let saved = null;
  try {
    saved = localStorage.getItem("se-theme");
  } catch {
    saved = null;
  }
  const prefersDark = window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches;
  applyTheme(saved || (prefersDark ? "dark" : "light"), false);
  $("#theme-toggle")?.addEventListener("click", () => {
    applyTheme(currentTheme() === "dark" ? "light" : "dark");
  });
}

/* --------------------------------------------------------------------------
   Profile / badges
   -------------------------------------------------------------------------- */

function displayName() {
  const name = (state.profile.name || "").trim();
  if (!name || name.toLowerCase().includes("mit-wpu student")) return "engineer";
  return name.split(" ")[0];
}

function initials() {
  const name = (state.profile.name || "").trim();
  if (!name || name.toLowerCase().includes("mit-wpu student")) return "MW";
  return name
    .split(/\s+/)
    .slice(0, 2)
    .map((part) => part.charAt(0).toUpperCase())
    .join("");
}

function updateProfileUI() {
  const name = state.profile.name || "MIT-WPU Student";
  const branch = state.profile.branch || "Computer Science";
  const avatarText = initials();
  const sidebarName = $("#sidebar-name");
  const sidebarBranch = $("#sidebar-branch");
  const sidebarAvatar = $("#sidebar-avatar");
  const topbarAvatar = $("#topbar-avatar");
  if (sidebarName) sidebarName.textContent = name;
  if (sidebarBranch) sidebarBranch.textContent = `${branch} · ${state.profile.year || "Student"}`;
  if (sidebarAvatar) sidebarAvatar.textContent = avatarText;
  if (topbarAvatar) topbarAvatar.textContent = avatarText;

  const aiPill = $("#ai-status-pill");
  const aiText = $("#ai-status-text");
  if (aiPill && aiText) {
    const aiOn = Boolean(state.features.ai);
    aiPill.classList.toggle("fallback", !aiOn);
    aiText.textContent = aiOn
      ? `Gemini · ${state.features.model || "2.5 Flash"}`
      : "Smart local fallback";
  }
}

function updateBadges() {
  const stats = state.stats || {};
  const setBadge = (id, value) => {
    const el = $(id);
    if (!el) return;
    if (value > 0) {
      el.textContent = value > 99 ? "99+" : String(value);
      el.hidden = false;
    } else {
      el.hidden = true;
    }
  };
  setBadge("#nav-task-badge", stats.tasks_open || 0);
  setBadge("#nav-campus-badge", (state.campus || []).filter((item) => item.urgency === "high" || item.urgency === "urgent").length);
  setBadge("#nav-saved-badge", stats.bookmarks || 0);
  const dot = $("#notification-dot");
  if (dot) dot.hidden = !(stats.overdue > 0 || stats.due_week > 0);
}

function setActiveView(view) {
  $$(".nav-item[data-nav], .mobile-nav a[data-nav]").forEach((link) => {
    const active = link.dataset.nav === view;
    link.classList.toggle("active", active);
    if (active) link.setAttribute("aria-current", "page");
    else link.removeAttribute("aria-current");
  });
  const meta = VIEW_META[view] || VIEW_META.overview;
  const title = $("#topbar-title");
  const eyebrow = $("#topbar-eyebrow");
  if (title) title.textContent = meta.title;
  if (eyebrow) eyebrow.textContent = meta.eyebrow;
  document.title = `${meta.title} · Student Ecosystem`;
}

/* --------------------------------------------------------------------------
   Router
   -------------------------------------------------------------------------- */

function currentView() {
  const hash = (window.location.hash || "").replace(/^#/, "").split("?")[0];
  return VIEW_META[hash] ? hash : "overview";
}

async function route() {
  const view = currentView();
  $$(".view").forEach((section) => section.classList.toggle("active", section.dataset.view === view));
  setActiveView(view);
  document.body.classList.remove("nav-open");
  $("#menu-btn")?.setAttribute("aria-expanded", "false");
  closeNotificationPanel();

  try {
    await enterView(view);
  } catch (error) {
    console.error("View failed:", view, error);
    toast(error.message || "This view could not load.", { type: "error", title: "Load failed" });
  }

  const wrap = $("#view-wrap");
  if (wrap && window.scrollY > 160) wrap.scrollIntoView({ behavior: "smooth", block: "start" });
  wrap?.focus({ preventScroll: true });
}

function navigate(view) {
  if (!VIEW_META[view]) view = "overview";
  if (window.location.hash === `#${view}`) route();
  else window.location.hash = view;
}

function rerenderActiveView() {
  const view = currentView();
  if (typeof renderView === "function") renderView(view);
}

/* --------------------------------------------------------------------------
   Modal
   -------------------------------------------------------------------------- */

function openModal({ eyebrow = "", title = "", body = "", footer = "", onMount }) {
  const overlay = $("#modal-overlay");
  if (!overlay) return;
  $("#modal-eyebrow").textContent = eyebrow;
  $("#modal-title").textContent = title;
  $("#modal-body").innerHTML = body;
  $("#modal-foot").innerHTML = footer;
  overlay.hidden = false;
  document.body.style.overflow = "hidden";
  requestAnimationFrame(() => {
    const focusable = overlay.querySelector("input, textarea, select, button");
    focusable?.focus();
  });
  if (typeof onMount === "function") onMount();
}

function closeModal() {
  const overlay = $("#modal-overlay");
  if (!overlay || overlay.hidden) return;
  overlay.hidden = true;
  document.body.style.overflow = "";
  $("#modal-body").innerHTML = "";
  $("#modal-foot").innerHTML = "";
}

/* --------------------------------------------------------------------------
   Notifications
   -------------------------------------------------------------------------- */

function closeNotificationPanel() {
  const panel = $("#notification-panel");
  if (panel) panel.hidden = true;
}

async function openNotificationPanel() {
  const panel = $("#notification-panel");
  if (!panel) return;
  if (!panel.hidden) {
    panel.hidden = true;
    return;
  }
  panel.hidden = false;
  const list = $("#notification-list");
  if (list) list.innerHTML = skeletonRows(3);
  try {
    const data = await api("/api/notifications");
    if (!list) return;
    if (!data.items || !data.items.length) {
      list.innerHTML = `<div class="empty-state compact"><div class="empty-icon">${icon("check")}</div><h3>All clear</h3><p>No deadlines in the next few days. Add tasks to keep it that way.</p></div>`;
      return;
    }
    list.innerHTML = data.items
      .map((item) => {
        const days = daysUntil(item.due_date);
        const color =
          days !== null && days < 0 ? "var(--danger)" : days !== null && days <= 2 ? "var(--warm)" : "var(--mint)";
        return `
          <a class="notification-item" href="#tasks">
            <span class="dot" style="background:${color}"></span>
            <div style="min-width:0">
              <strong>${esc(item.title)}</strong>
              <small>${esc(item.subtitle)}</small>
            </div>
          </a>`;
      })
      .join("");
  } catch (error) {
    if (list) list.innerHTML = `<div class="empty-state compact"><p>${esc(error.message)}</p></div>`;
  }
}

/* --------------------------------------------------------------------------
   Command palette
   -------------------------------------------------------------------------- */

const PALETTE_NAV = Object.entries(VIEW_META).map(([key, meta]) => ({
  key,
  title: meta.title,
  subtitle: meta.eyebrow,
  icon: {
    overview: "home",
    campus: "campus",
    opportunities: "trophy",
    news: "news",
    mail: "sparkles",
    vault: "book",
    tasks: "tasks",
    saved: "bookmark",
    settings: "settings",
  }[key],
}));

function paletteGroup(title) {
  return `<div class="palette-group">${esc(title)}</div>`;
}

function paletteItem({ title, subtitle, icon: iconName, badge = "", attributes = "" }) {
  return `
    <button type="button" class="palette-item" ${attributes}>
      <span class="p-icon">${icon(iconName)}</span>
      <span class="p-copy"><strong>${esc(title)}</strong><small>${esc(subtitle)}</small></span>
      ${badge ? `<span class="p-badge">${esc(badge)}</span>` : ""}
    </button>`;
}

function renderPalette(query = "", data = null) {
  const results = $("#palette-results");
  if (!results) return;
  const needle = query.trim().toLowerCase();
  const navMatches = PALETTE_NAV.filter(
    (item) => !needle || item.title.toLowerCase().includes(needle) || item.subtitle.toLowerCase().includes(needle)
  );

  let html = "";
  if (navMatches.length) {
    html += paletteGroup(needle ? "Views" : "Jump to");
    html += navMatches
      .map((item) =>
        paletteItem({
          title: item.title,
          subtitle: item.subtitle,
          icon: item.icon,
          badge: "View",
          attributes: `data-palette="nav" data-value="${esc(item.key)}"`,
        })
      )
      .join("");
  }

  if (data) {
    const groups = [
      ["Tasks", data.tasks, "tasks", (item) => ({ title: item.title, subtitle: item.due_date ? `Due ${fmtDate(item.due_date)}` : "No due date", badge: item.priority })],
      ["Opportunities", data.opportunities, "trophy", (item) => ({ title: item.title, subtitle: item.organizer || item.track, badge: item.deadline ? fmtDate(item.deadline) : "Rolling" })],
      ["Academic vault", data.vault, "book", (item) => ({ title: item.title, subtitle: item.subject, badge: item.type })],
      ["Saved summaries", data.summaries, "mail", (item) => ({ title: item.subject, subtitle: item.tldr, badge: item.category })],
      ["Bookmarks", data.bookmarks, "bookmark", (item) => ({ title: item.title, subtitle: item.subtitle, badge: item.type })],
    ];
    groups.forEach(([label, items, iconName, map]) => {
      if (!items || !items.length) return;
      html += paletteGroup(label);
      html += items
        .map((item) => {
          const view = map(item);
          return paletteItem({
            title: view.title || "Untitled",
            subtitle: view.subtitle || "",
            icon: iconName,
            badge: view.badge || "",
            attributes: `data-palette="${label.toLowerCase()}" data-value="${esc(item.id || item.title || "")}"`,
          });
        })
        .join("");
    });
  }

  if (!html) {
    html = `<div class="palette-empty">No matches for “${esc(query)}”. Try a task, subject, hackathon or notice.</div>`;
  }
  results.innerHTML = html;
  state.paletteOptions = $$(".palette-item", results);
  state.paletteSelection = 0;
  highlightPalette();
}

function highlightPalette() {
  state.paletteOptions.forEach((el, index) => el.classList.toggle("active", index === state.paletteSelection));
  state.paletteOptions[state.paletteSelection]?.scrollIntoView({ block: "nearest" });
}

async function runPaletteSearch(query) {
  if (query.trim().length < 2) {
    renderPalette(query, null);
    return;
  }
  try {
    const data = await api(`/api/search?q=${encodeURIComponent(query)}`);
    renderPalette(query, data);
  } catch {
    renderPalette(query, null);
  }
}

const debouncedPaletteSearch = debounce(runPaletteSearch, 240);

function openPalette() {
  const overlay = $("#palette-overlay");
  if (!overlay) return;
  overlay.hidden = false;
  document.body.style.overflow = "hidden";
  const input = $("#palette-input");
  if (input) {
    input.value = "";
    input.focus();
  }
  renderPalette("", null);
}

function closePalette() {
  const overlay = $("#palette-overlay");
  if (!overlay || overlay.hidden) return;
  overlay.hidden = true;
  if ($("#modal-overlay")?.hidden !== false) document.body.style.overflow = "";
}

async function activatePaletteOption(option) {
  if (!option) return;
  const kind = option.dataset.palette;
  const value = option.dataset.value;
  closePalette();

  if (kind === "nav") {
    navigate(value);
    return;
  }

  if (kind === "tasks") {
    const task = state.tasks.find((item) => String(item.id) === value);
    navigate("tasks");
    if (task) {
      state.filters.taskQuery = task.title;
      const input = $("#task-search");
      if (input) input.value = task.title;
      setTimeout(() => renderTasks(), 60);
    }
    return;
  }

  if (kind === "opportunities") {
    navigate("opportunities");
    const item = state.opportunities.find((entry) => String(entry.id) === value);
    if (item) {
      state.filters.oppQuery = item.title;
      const input = $("#opp-search");
      if (input) input.value = item.title;
      setTimeout(() => renderOpportunities(), 60);
    }
    return;
  }

  if (kind === "academic vault") {
    navigate("vault");
    const item = state.vault.find((entry) => String(entry.id) === value);
    if (item) {
      state.filters.vaultQuery = item.title;
      const input = $("#vault-search");
      if (input) input.value = item.title;
      setTimeout(() => renderVault(), 60);
    }
    return;
  }

  if (kind === "saved summaries") {
    navigate("mail");
    setTimeout(() => openSummaryById(value), 120);
    return;
  }

  if (kind === "bookmarks") {
    navigate("saved");
    return;
  }
}

/* --------------------------------------------------------------------------
   Global keyboard & overlay dismissal
   -------------------------------------------------------------------------- */

function isTypingTarget(target) {
  if (!target) return false;
  const tag = target.tagName;
  return tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT" || target.isContentEditable;
}

function initGlobalShortcuts() {
  document.addEventListener("keydown", (event) => {
    const paletteOpen = $("#palette-overlay") && !$("#palette-overlay").hidden;
    const modalOpen = $("#modal-overlay") && !$("#modal-overlay").hidden;

    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
      event.preventDefault();
      if (paletteOpen) closePalette();
      else openPalette();
      return;
    }

    if (event.key === "/" && !isTypingTarget(event.target) && !paletteOpen && !modalOpen) {
      event.preventDefault();
      openPalette();
      return;
    }

    if (event.key === "Escape") {
      if (paletteOpen) closePalette();
      else if (modalOpen) closeModal();
      else {
        document.body.classList.remove("nav-open");
        closeNotificationPanel();
      }
      return;
    }

    if (paletteOpen) {
      if (event.key === "ArrowDown") {
        event.preventDefault();
        state.paletteSelection = Math.min(state.paletteSelection + 1, state.paletteOptions.length - 1);
        highlightPalette();
      } else if (event.key === "ArrowUp") {
        event.preventDefault();
        state.paletteSelection = Math.max(state.paletteSelection - 1, 0);
        highlightPalette();
      } else if (event.key === "Enter") {
        event.preventDefault();
        activatePaletteOption(state.paletteOptions[state.paletteSelection]);
      }
    }
  });
}

/* --------------------------------------------------------------------------
   Bootstrap helpers
   -------------------------------------------------------------------------- */

function greeting() {
  const hour = new Date().getHours();
  if (hour < 5) return "Still up";
  if (hour < 12) return "Good morning";
  if (hour < 17) return "Good afternoon";
  return "Good evening";
}

function todayLong() {
  return new Intl.DateTimeFormat("en-IN", {
    weekday: "long",
    day: "numeric",
    month: "long",
  }).format(new Date());
}

function updateClockUI() {
  const today = $("#today-label");
  if (today) today.textContent = todayLong();
  const year = $("#footer-year");
  if (year) year.textContent = `© ${new Date().getFullYear()}`;
}

async function loadBookmarks() {
  try {
    const data = await api("/api/bookmarks");
    state.bookmarks = data.bookmarks || [];
    syncSavedKeys();
  } catch {
    state.bookmarks = [];
    state.savedKeys = new Set();
  }
}

function initStatsUI() {
  updateProfileUI();
  updateBadges();
}
