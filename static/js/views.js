"use strict";

/* ==========================================================================
   STUDENT ECOSYSTEM — VIEWS
   Data loaders and renderers for every module.
   ========================================================================== */

/* --------------------------------------------------------------------------
   Data fetchers
   -------------------------------------------------------------------------- */

async function fetchCampus(limit = 14, force = false) {
  const data = await api(`/api/college-updates?limit=${limit}${force ? "&refresh=true" : ""}`);
  state.campus = data.updates || [];
  state.campusCategories = data.categories || {};
  state.campusStatus = data.status || null;
  state.campusUpdated = data.updated_at || "";
  state.loaded.campus = true;
  updateBadges();
  return data;
}

async function fetchOpportunities(force = false) {
  const data = await api(`/api/opportunities${force ? "?refresh=true" : ""}`);
  state.opportunities = data.opportunities || [];
  state.oppTracks = data.tracks || [];
  state.loaded.opportunities = true;
  return data;
}

async function fetchNews(limit = 12, force = false) {
  const branch = state.profile.branch || "Computer Science";
  const data = await api(
    `/api/news?branch=${encodeURIComponent(branch)}&limit=${limit}${force ? "&refresh=true" : ""}`,
    { timeout: 70000 }
  );
  state.news = data.articles || [];
  state.newsMeta = data;
  state.loaded.news = true;
  return data;
}

async function fetchTasks(force = false) {
  const data = await api(`/api/tasks${force ? `?t=${Date.now()}` : ""}`);
  state.tasks = data.tasks || [];
  state.taskCounts = data.counts || { todo: 0, doing: 0, done: 0 };
  if (data.stats) state.stats = data.stats;
  state.loaded.tasks = true;
  updateBadges();
  return data;
}

async function fetchVault(force = false) {
  const data = await api(`/api/vault${force ? `?t=${Date.now()}` : ""}`);
  state.vault = data.resources || [];
  state.vaultSubjects = data.subjects || [];
  state.vaultTypes = data.types || [];
  if (data.stats) state.stats = data.stats;
  state.loaded.vault = true;
  return data;
}

async function fetchSummaries(force = false) {
  const data = await api(`/api/summaries${force ? `?t=${Date.now()}` : ""}`);
  state.summaries = data.summaries || [];
  state.loaded.mail = true;
  return data;
}

async function loadSaved(force = false) {
  if (!force && state.loaded.saved) {
    renderSaved();
    return;
  }
  const data = await api("/api/bookmarks");
  state.bookmarks = data.bookmarks || [];
  syncSavedKeys();
  state.loaded.saved = true;
  renderSaved();
}

/* --------------------------------------------------------------------------
   Router entry
   -------------------------------------------------------------------------- */

async function enterView(view) {
  if (view === "overview") return loadOverview();
  if (view === "campus") return loadCampusView();
  if (view === "opportunities") return loadOpportunitiesView();
  if (view === "news") return loadNewsView();
  if (view === "mail") return loadMailView();
  if (view === "vault") return loadVaultView();
  if (view === "tasks") return loadTasksView();
  if (view === "saved") return loadSaved();
  if (view === "settings") return renderSettings();
}

function renderView(view) {
  if (view === "overview") renderOverview();
  else if (view === "campus") renderCampus();
  else if (view === "opportunities") renderOpportunities();
  else if (view === "news") renderNews();
  else if (view === "vault") renderVault();
  else if (view === "tasks") renderTasks();
  else if (view === "saved") renderSaved();
  else if (view === "settings") renderSettings();
  else if (view === "mail") renderMailHistory();
}

/* --------------------------------------------------------------------------
   Overview
   -------------------------------------------------------------------------- */

async function loadOverview(force = false) {
  if (!state.loaded.overview || force) {
    const stats = $("#overview-stats");
    if (stats) stats.innerHTML = Array.from({ length: 4 }, () => `<div class="skeleton" style="height:76px;border-radius:16px"></div>`).join("");
    const briefing = $("#briefing-body");
    if (briefing) briefing.innerHTML = skeletonPanel("Loading your daily briefing");
    const lineup = $("#overview-lineup");
    if (lineup) lineup.innerHTML = skeletonRows(3);
    const deadlines = $("#overview-deadlines");
    if (deadlines) deadlines.innerHTML = skeletonRows(4);

    const jobs = [
      api("/api/briefing").then((data) => {
        state.briefing = data.briefing;
        if (data.stats) state.stats = data.stats;
      }),
      fetchTasks(),
      fetchCampus(6),
    ];
    if (!state.loaded.opportunities) jobs.push(fetchOpportunities());
    if (!state.loaded.vault) jobs.push(fetchVault());
    if (!state.loaded.mail) jobs.push(fetchSummaries());

    const results = await Promise.allSettled(jobs);
    const failures = results.filter((result) => result.status === "rejected");
    state.loaded.overview = true;
    if (failures.length === results.length) {
      throw failures[0].reason || new Error("The overview could not load.");
    }
    renderOverview();
  } else {
    renderOverview();
  }

  // Load a tiny news slice after the dashboard is already visible.
  if (!state.loaded.news) {
    fetchNews(3)
      .then(() => {
        if (currentView() === "overview") renderOverview();
      })
      .catch(() => {});
  }
}

function renderOverview() {
  const name = displayName();
  const title = $("#greeting-title");
  if (title) title.textContent = `${greeting()}, ${name}.`;
  const sub = $("#greeting-sub");
  if (sub) {
    sub.textContent = state.briefing?.summary
      ? state.briefing.summary
      : "Here is what matters at MIT-WPU today — campus updates, deadlines, opportunities and engineering news, distilled.";
  }
  const mode = $("#hero-mode");
  if (mode) {
    mode.textContent = state.features.ai ? "Gemini summaries on" : "Smart local summaries";
  }
  updateClockUI();
  renderOverviewStats();
  renderFocusCard();
  renderBriefing();
  renderLineup();
  renderDeadlines();
  renderQuickTiles();
  updateBadges();
}

function renderOverviewStats() {
  const container = $("#overview-stats");
  if (!container) return;
  const stats = state.stats || {};
  const campusAlerts = (state.campus || []).filter((item) => ["high", "urgent"].includes(item.urgency)).length;
  const cards = [
    {
      value: stats.due_week ?? 0,
      label: "Due this week",
      icon: "calendar",
      tone: "warm",
      trend: stats.overdue ? `${stats.overdue} overdue` : "You're on track",
    },
    {
      value: stats.tasks_open ?? 0,
      label: "Open tasks",
      icon: "tasks",
      tone: "",
      trend: `${stats.tasks_done ?? 0} completed`,
    },
    {
      value: stats.bookmarks ?? 0,
      label: "Saved for later",
      icon: "bookmark",
      tone: "gold",
      trend: `${stats.summaries ?? 0} notices summarized`,
    },
    {
      value: campusAlerts,
      label: "Campus alerts",
      icon: "campus",
      tone: "mint",
      trend: state.campusStatus?.mode === "live" ? "Live from MIT-WPU" : "Curated campus guide",
    },
  ];

  container.innerHTML = cards
    .map(
      (card) => `
      <article class="stat-card">
        <span class="stat-icon ${card.tone}">${icon(card.icon)}</span>
        <span class="stat-copy">
          <strong>${esc(card.value)}</strong>
          <span>${esc(card.label)}</span>
          <span class="trend">${esc(card.trend)}</span>
        </span>
      </article>`
    )
    .join("");
}

function renderFocusCard() {
  const stats = state.stats || {};
  const open = Number(stats.tasks_open || 0);
  const done = Number(stats.tasks_done || 0);
  const total = open + done;
  const progress = total ? Math.round((done / total) * 100) : 0;
  const ring = $("#focus-ring");
  if (ring) ring.style.setProperty("--progress", progress);
  const doneEl = $("#focus-done");
  if (doneEl) doneEl.textContent = done;
  const totalEl = $("#focus-total");
  if (totalEl) totalEl.textContent = total || 0;
  const bar = $("#focus-bar");
  if (bar) bar.style.width = `${progress}%`;
  const count = $("#focus-count");
  if (count) count.textContent = plural(open, "open task");

  const headline = $("#focus-headline");
  if (headline) headline.textContent = state.briefing?.headline || (open ? `${open} things need your attention` : "Make today count");
  const summary = $("#focus-summary");
  if (summary) {
    summary.textContent =
      state.briefing?.summary ||
      "Pick one campus update, one opportunity and one task. Small, deliberate progress compounds.";
  }

  const upcoming = nextDeadline();
  const next = $("#focus-next");
  if (next) {
    next.textContent = upcoming
      ? `${upcoming.title} · ${deadlineLabel(upcoming.date).text}`
      : "No deadlines this week — get ahead";
  }
}

function nextDeadline() {
  const today = new Date().toISOString().slice(0, 10);
  const candidates = [];
  (state.tasks || []).forEach((task) => {
    if (task.status !== "done" && task.due_date) candidates.push({ title: task.title, date: task.due_date });
  });
  (state.campus || []).forEach((item) => {
    if (item.deadline) candidates.push({ title: item.title, date: item.deadline });
  });
  const upcoming = candidates.filter((item) => String(item.date) >= today);
  upcoming.sort((a, b) => String(a.date).localeCompare(String(b.date)));
  return upcoming[0] || null;
}

function renderBriefing() {
  const container = $("#briefing-body");
  if (!container) return;
  const briefing = state.briefing;
  if (!briefing) {
    container.innerHTML = emptyState("sparkles", "Your briefing is warming up", "Add a few tasks or refresh to generate today's priorities.");
    return;
  }
  const priorities = (briefing.priorities || []).slice(0, 3);
  container.innerHTML = `
    <p class="briefing-summary">${esc(briefing.summary || "Your day is clear — use it to get ahead.")}</p>
    <div class="briefing-priorities">
      ${priorities
        .map(
          (item, index) => `
        <div class="briefing-priority">
          <span class="priority-index">${index + 1}</span>
          <span>${esc(item)}</span>
        </div>`
        )
        .join("")}
    </div>
    <div class="briefing-mode">
      ${icon("sparkles")}
      <span>${briefing.mode === "ai" ? "Written by Gemini from your live context" : "Generated locally from your live context"}</span>
      <span>·</span>
      <span>${esc(briefing.generated_at ? timeAgo(briefing.generated_at) : "just now")}</span>
    </div>`;
}

function renderLineup() {
  const container = $("#overview-lineup");
  if (!container) return;
  const today = new Date().toISOString().slice(0, 10);
  const campus =
    (state.campus || []).find((item) => !item.deadline || item.deadline >= today) || (state.campus || [])[0];
  const items = [];
  const opportunity = (state.opportunities || []).find((item) => !item.deadline_passed) || state.opportunities?.[0];
  const news = (state.news || [])[0];
  const task = (state.tasks || []).find((item) => item.status !== "done");
  const resource = (state.vault || []).find((item) => item.starred) || state.vault?.[0];

  if (campus) {
    const deadline = campus.deadline ? ` · ${deadlineLabel(campus.deadline).text}` : "";
    items.push({
      href: "#campus",
      icon: "campus",
      tone: "warm",
      title: campus.title,
      meta: `MIT-WPU · ${campus.category}${deadline}`,
    });
  }
  if (opportunity) {
    items.push({
      href: "#opportunities",
      icon: "trophy",
      tone: "",
      title: opportunity.title,
      meta: `${opportunity.track} · ${opportunity.deadline ? deadlineLabel(opportunity.deadline).text : "Rolling"}`,
    });
  }
  if (news) {
    items.push({
      href: "#news",
      icon: "news",
      tone: "mint",
      title: news.title,
      meta: `${news.source}${news.published_at ? ` · ${timeAgo(news.published_at)}` : ""}`,
    });
  } else if (task) {
    items.push({
      href: "#tasks",
      icon: "tasks",
      tone: "mint",
      title: task.title,
      meta: `${task.due_date ? deadlineLabel(task.due_date).text : "No due date"} · ${task.priority} priority`,
    });
  } else if (resource) {
    items.push({
      href: "#vault",
      icon: "book",
      tone: "mint",
      title: resource.title,
      meta: `${resource.subject} · ${resource.type}`,
    });
  }

  if (!items.length) {
    container.innerHTML = emptyState("compass", "Nothing queued yet", "Load campus updates and the opportunity radar to populate your day.");
    return;
  }

  container.innerHTML = items
    .slice(0, 3)
    .map(
      (item) => `
      <a class="lineup-item" href="${esc(item.href)}">
        <span class="lineup-icon ${item.tone}">${icon(item.icon)}</span>
        <span class="lineup-copy">
          <strong>${esc(item.title)}</strong>
          <span>${icon("clock")}${esc(item.meta)}</span>
        </span>
        ${icon("chevron-right")}
      </a>`
    )
    .join("");
}

function renderDeadlines() {
  const container = $("#overview-deadlines");
  if (!container) return;
  const today = new Date().toISOString().slice(0, 10);
  const items = [];
  (state.tasks || []).forEach((task) => {
    if (task.status !== "done" && task.due_date) {
      items.push({
        date: task.due_date,
        title: task.title,
        meta: `Task · ${task.priority} priority`,
        href: "#tasks",
      });
    }
  });
  (state.campus || []).forEach((item) => {
    if (item.deadline) {
      items.push({
        date: item.deadline,
        title: item.title,
        meta: `MIT-WPU · ${item.category}`,
        href: "#campus",
      });
    }
  });
  (state.opportunities || []).forEach((item) => {
    const date = item.deadline || item.close_date;
    if (date) {
      items.push({
        date,
        title: item.title,
        meta: `Opportunity · ${item.mode || item.location || "Open"}`,
        href: "#opportunities",
      });
    }
  });
  const upcoming = items.filter((item) => String(item.date) >= today);
  upcoming.sort((a, b) => String(a.date).localeCompare(String(b.date)));
  if (!upcoming.length) {
    container.innerHTML = `
      <div class="empty-state compact">
        <div class="empty-icon">${icon("calendar")}</div>
        <h3>No deadlines yet</h3>
        <p>Add a task or convert a campus notice into a deadline and it will show up here.</p>
        <a class="btn btn-secondary btn-sm" href="#tasks">Open task hub</a>
      </div>`;
    return;
  }

  container.innerHTML = upcoming
    .slice(0, 5)
    .map((item) => {
      const date = parseDate(item.date);
      const days = daysUntil(item.date);
      const month = date ? new Intl.DateTimeFormat("en-IN", { month: "short" }).format(date) : "—";
      const day = date ? date.getDate() : "—";
      return `
        <a class="deadline-row" href="${esc(item.href)}">
          <span class="deadline-date ${days !== null && days <= 3 ? "soon" : ""}">
            <strong>${esc(day)}</strong><small>${esc(month)}</small>
          </span>
          <span class="deadline-copy">
            <strong>${esc(item.title)}</strong>
            <span>${esc(item.meta)} · ${esc(deadlineLabel(item.date).text)}</span>
          </span>
          ${icon("chevron-right")}
        </a>`;
    })
    .join("");
}

function renderQuickTiles() {
  const container = $("#overview-quick");
  if (!container) return;
  const tiles = [
    { href: "#mail", icon: "sparkles", title: "Summarize a notice", meta: `${state.stats.summaries ?? 0} saved summaries` },
    { href: "#opportunities", icon: "trophy", title: "Scan opportunities", meta: `${state.opportunities.length} live listings` },
    { href: "#vault", icon: "book", title: "Open the vault", meta: `${state.stats.vault ?? 0} resources` },
    { href: "#news", icon: "news", title: "Read your briefing", meta: state.profile.branch },
  ];
  container.innerHTML = tiles
    .map(
      (tile) => `
      <a class="quick-tile" href="${esc(tile.href)}">
        <span class="quick-icon">${icon(tile.icon)}</span>
        <span style="min-width:0">
          <strong>${esc(tile.title)}</strong>
          <span>${esc(tile.meta)}</span>
        </span>
      </a>`
    )
    .join("");
}

/* --------------------------------------------------------------------------
   Campus
   -------------------------------------------------------------------------- */

async function loadCampusView(force = false) {
  if (!state.loaded.campus || force) {
    const grid = $("#campus-grid");
    if (grid) grid.innerHTML = skeletonCards(4);
    await fetchCampus(14, force);
  }
  renderCampus();
}

function renderCampus() {
  const grid = $("#campus-grid");
  if (!grid) return;
  const all = state.campus || [];
  const query = state.filters.campusQuery.trim().toLowerCase();
  const category = state.filters.campusCategory;

  const filtered = all.filter((item) => {
    const matchesCategory = category === "All" || item.category === category;
    const haystack = `${item.title} ${item.description} ${(item.tags || []).join(" ")} ${item.category}`.toLowerCase();
    return matchesCategory && (!query || haystack.includes(query));
  });

  renderCampusSource();
  renderCampusCategories();
  grid.classList.add("feed-grid");

  if (!filtered.length) {
    grid.innerHTML = emptyState(
      "campus",
      query || category !== "All" ? "No updates match this filter" : "Campus feed is empty",
      query || category !== "All"
        ? "Try a different category or clear the search."
        : "Refresh to scan the MIT-WPU website again. The curated guide is always available.",
      `<button class="btn btn-secondary" type="button" data-action="refresh-campus">${icon("refresh")}Refresh campus feed</button>`
    );
    return;
  }

  grid.innerHTML = filtered.map(campusCard).join("");
}

function renderCampusSource() {
  const container = $("#campus-source");
  if (!container) return;
  const status = state.campusStatus || {};
  const live = status.mode === "live";
  const configured = state.college?.url || "";
  container.className = `source-strip ${live ? "" : "curated"}`;
  container.innerHTML = `
    <span class="live-dot"></span>
    <strong>${live ? "Live campus scan" : "Curated campus guide"}</strong>
    <span class="sep">·</span>
    <span>${live ? `${status.live_count || 0} live links` : "Official site not reachable from this environment"}</span>
    <span class="sep">·</span>
    <span>${configured ? esc(configured.replace(/^https?:\/\//, "")) : "No college URL configured"}</span>
    <span class="spacer"></span>
    <span>${state.campusUpdated ? `Updated ${timeAgo(state.campusUpdated)}` : "Just now"}</span>
    ${state.features.ai ? `<span class="pill pill-primary">${icon("sparkles")}AI enriched</span>` : `<span class="pill pill-soft">Local summaries</span>`}`;
}

function renderCampusCategories() {
  const container = $("#campus-categories");
  if (!container) return;
  const counts = {};
  (state.campus || []).forEach((item) => {
    counts[item.category] = (counts[item.category] || 0) + 1;
  });
  const categories = ["All", ...Object.keys(counts).sort((a, b) => counts[b] - counts[a])];
  container.innerHTML = categories
    .map(
      (category) => `
      <button class="chip ${state.filters.campusCategory === category ? "active" : ""}" type="button" role="tab" aria-selected="${state.filters.campusCategory === category}" data-action="filter-campus-category" data-value="${esc(category)}">
        ${esc(category)} ${category === "All" ? `<span class="count">${state.campus.length}</span>` : `<span class="count">${counts[category]}</span>`}
      </button>`
    )
    .join("");
}

function campusCard(item) {
  const saved = isSaved("campus", item.id);
  const deadline = deadlineLabel(item.deadline);
  const tldr = item.tldr || truncate(item.description, 240) || "Open the official link for full details.";
  const actions = (item.what_to_do || []).slice(0, 3);
  const url = safeUrl(item.link);
  const published = item.published_at ? timeAgo(item.published_at) : "";
  return `
    <article class="feed-card" data-id="${esc(item.id)}">
      <div class="card-top">
        <span class="pill pill-primary">${esc(item.category || "Campus")}</span>
        <span class="pill ${urgencyClass(item.urgency)}">${esc(urgencyLabel(item.urgency))}</span>
        ${item.deadline ? `<span class="pill pill-deadline ${deadline.cls}">${icon("clock")}${esc(deadline.text)}</span>` : ""}
        ${item.whats_new && !item.curated && !(Number(item.days_left) < 0) ? `<span class="pill pill-mint">New</span>` : ""}
        <span class="spacer"></span>
        <button class="icon-action ${saved ? "active" : ""}" type="button" aria-label="${saved ? "Remove bookmark" : "Save update"}" data-action="toggle-save" data-kind="campus" data-id="${esc(item.id)}">${icon("bookmark")}</button>
      </div>
      <h3 class="card-title">
        ${url ? `<a href="${esc(url)}" target="_blank" rel="noopener noreferrer">${esc(item.title)}</a>` : esc(item.title)}
      </h3>
      <p class="card-desc">${esc(truncate(item.description, 220))}</p>
      <div class="ai-block">
        <div class="ai-label">${icon("sparkles")}TL;DR</div>
        <p class="ai-tldr">${esc(tldr)}</p>
        ${actions.length ? `<div class="ai-actions-label">What to do</div><ul class="ai-actions">${actions.map((action) => `<li>${esc(action)}</li>`).join("")}</ul>` : ""}
      </div>
      <div class="card-foot">
        <span class="card-meta">${item.curated ? icon("book") : icon("campus")}<span>${item.curated ? "Curated guide" : "MIT-WPU official"}${published ? ` · ${published}` : ""}</span></span>
        <span class="spacer"></span>
        <button class="icon-action" type="button" title="Add to tasks" aria-label="Add to tasks" data-action="task-from" data-kind="campus" data-id="${esc(item.id)}">${icon("plus")}</button>
        ${url ? `<a class="icon-action" href="${esc(url)}" target="_blank" rel="noopener noreferrer" title="Open official source" aria-label="Open official source">${icon("external")}</a>` : ""}
      </div>
    </article>`;
}

/* --------------------------------------------------------------------------
   Opportunities
   -------------------------------------------------------------------------- */

async function loadOpportunitiesView(force = false) {
  if (!state.loaded.opportunities || force) {
    const grid = $("#opp-grid");
    if (grid) grid.innerHTML = skeletonCards(6);
    await fetchOpportunities(false);
    // Refresh saved flags from server.
    if (!state.loaded.saved) {
      try {
        const data = await api("/api/bookmarks");
        state.bookmarks = data.bookmarks || [];
        syncSavedKeys();
      } catch {
        /* saved flags are a nicety */
      }
    }
  }
  renderOpportunities();
}

function filteredOpportunities() {
  const query = state.filters.oppQuery.trim().toLowerCase();
  const track = state.filters.oppTrack;
  const mode = state.filters.oppMode;
  const deadline = state.filters.oppDeadline;
  return (state.opportunities || []).filter((item) => {
    if (track !== "All" && item.track !== track) return false;
    if (mode !== "All" && item.mode !== mode) return false;
    if (state.filters.oppSaved && !isSaved("opportunity", item.id)) return false;
    const haystack = `${item.title} ${item.organizer} ${item.description} ${item.location} ${(item.tags || []).join(" ")}`.toLowerCase();
    if (query && !haystack.includes(query)) return false;
    if (deadline) {
      const days = daysUntil(item.deadline);
      if (deadline === "open" && item.deadline && days !== null && days < 0) return false;
      if (deadline === "7" && (days === null || days < 0 || days > 7)) return false;
      if (deadline === "30" && (days === null || days < 0 || days > 30)) return false;
    }
    return true;
  });
}

function renderOpportunities() {
  const grid = $("#opp-grid");
  if (!grid) return;
  renderOpportunityStats();
  renderOpportunityTracks();

  const filtered = filteredOpportunities();
  if (!filtered.length) {
    grid.innerHTML = emptyState(
      "trophy",
      "No opportunities match those filters",
      "Broaden the track, mode or deadline window — or clear the search.",
      `<button class="btn btn-secondary" type="button" data-action="reset-opp-filters">${icon("refresh")}Reset filters</button>`
    );
    return;
  }
  grid.innerHTML = filtered.map(opportunityCard).join("");
}

function renderOpportunityStats() {
  const container = $("#opp-stats");
  if (!container) return;
  const all = state.opportunities || [];
  const saved = all.filter((item) => isSaved("opportunity", item.id)).length;
  const closing = all.filter((item) => {
    const days = daysUntil(item.deadline);
    return days !== null && days >= 0 && days <= 7;
  }).length;
  const online = all.filter((item) => item.mode === "Online").length;
  const cards = [
    { value: all.length, label: "Curated opportunities", icon: "trophy", tone: "" },
    { value: closing, label: "Closing this week", icon: "clock", tone: "warm" },
    { value: saved, label: "Saved to your radar", icon: "bookmark", tone: "gold" },
    { value: online, label: "Fully online", icon: "compass", tone: "mint" },
  ];
  container.innerHTML = cards
    .map(
      (card) => `
      <div class="opp-stat">
        <span class="stat-icon ${card.tone}">${icon(card.icon)}</span>
        <div><strong>${esc(card.value)}</strong><span>${esc(card.label)}</span></div>
      </div>`
    )
    .join("");
}

function renderOpportunityTracks() {
  const container = $("#opp-tracks");
  if (!container) return;
  const counts = {};
  (state.opportunities || []).forEach((item) => {
    counts[item.track] = (counts[item.track] || 0) + 1;
  });
  const tracks = ["All", ...state.oppTracks];
  container.innerHTML = tracks
    .map(
      (track) => `
      <button class="chip ${state.filters.oppTrack === track ? "active" : ""}" type="button" data-action="filter-opp-track" data-value="${esc(track)}">
        ${esc(track)} <span class="count">${track === "All" ? state.opportunities.length : counts[track] || 0}</span>
      </button>`
    )
    .join("") +
    `<button class="chip ${state.filters.oppSaved ? "active" : ""}" type="button" data-action="toggle-opp-saved">${icon("bookmark")}Saved</button>`;
}

function opportunityCard(item) {
  const saved = isSaved("opportunity", item.id);
  const deadline = deadlineLabel(item.deadline);
  const days = daysUntil(item.deadline);
  const url = safeUrl(item.url);
  const urgent = days !== null && days >= 0 && days <= 7;
  const trackClass = String(item.track || "Hackathon").toLowerCase().replace(/\s+/g, "-");
  return `
    <article class="opp-card track-${esc(trackClass)}" data-id="${esc(item.id)}">
      <div class="opp-top">
        <span class="pill opp-track">${esc(item.track)}</span>
        <span class="pill ${item.mode === "Online" ? "pill-mint" : item.mode === "Hybrid" ? "pill-warm" : "pill-soft"}">${esc(item.mode)}</span>
        <span class="spacer"></span>
        <button class="icon-action ${saved ? "active" : ""}" type="button" aria-label="${saved ? "Remove bookmark" : "Save opportunity"}" data-action="toggle-save" data-kind="opportunity" data-id="${esc(item.id)}">${icon("bookmark")}</button>
      </div>
      <h3 class="opp-title">${esc(item.title)}</h3>
      <p class="opp-organizer">${icon("users")}${esc(item.organizer)}</p>
      <p class="opp-desc">${esc(item.description)}</p>
      <div class="opp-why">
        <span>${icon("sparkles")}Why it's worth it</span>
        <p>${esc(item.why)}</p>
      </div>
      <div class="opp-meta">
        <div class="opp-meta-item"><span>Deadline</span><strong>${item.deadline ? esc(fmtDate(item.deadline)) : "Rolling"}</strong></div>
        <div class="opp-meta-item"><span>Mode</span><strong>${esc(item.mode)}</strong><strong class="small">${esc(item.location || "")}</strong></div>
        <div class="opp-meta-item"><span>Prize / perks</span><strong>${esc(truncate(item.prize || "Varies", 70))}</strong></div>
        <div class="opp-meta-item"><span>Starts</span><strong>${item.starts_at ? esc(fmtDate(item.starts_at)) : "See official page"}</strong></div>
      </div>
      <div class="opp-tags">${(item.tags || []).slice(0, 4).map((tag) => `<span class="opp-tag">${esc(tag)}</span>`).join("")}</div>
      <div class="opp-foot">
        <span class="opp-deadline ${urgent ? "urgent" : ""}">${icon("clock")}${esc(deadline.text)}</span>
        <span class="spacer"></span>
        <button class="icon-action" type="button" title="Add deadline to tasks" aria-label="Add deadline to tasks" data-action="task-from" data-kind="opportunity" data-id="${esc(item.id)}">${icon("calendar")}</button>
        ${url ? `<a class="apply-link" href="${esc(url)}" target="_blank" rel="noopener noreferrer">Apply ${icon("external")}</a>` : `<span class="pill pill-soft">Link unavailable</span>`}
      </div>
    </article>`;
}

/* --------------------------------------------------------------------------
   News
   -------------------------------------------------------------------------- */

async function loadNewsView(force = false) {
  if (!state.loaded.news || force) {
    const grid = $("#news-grid");
    if (grid) grid.innerHTML = skeletonCards(6);
    const select = $("#news-branch");
    if (select && !select.options.length) {
      select.innerHTML = (state.branches || []).map((branch) => `<option value="${esc(branch)}">${esc(branch)}</option>`).join("");
      select.value = state.profile.branch;
    }
    await fetchNews(12, force);
  }
  renderNews();
}

function renderNews() {
  const grid = $("#news-grid");
  if (!grid) return;
  const query = state.filters.newsQuery.trim().toLowerCase();
  const filtered = (state.news || []).filter((item) => {
    if (!query) return true;
    const haystack = `${item.title} ${item.description} ${item.source} ${(item.tags || []).join(" ")} ${(item.bullets || []).join(" ")}`.toLowerCase();
    return haystack.includes(query);
  });

  renderNewsSource();
  const countLabel = $("#news-count-label");
  if (countLabel) countLabel.textContent = `${plural(filtered.length, "briefing")} for ${state.profile.branch}`;

  if (!filtered.length) {
    grid.innerHTML = emptyState(
      "news",
      query ? "No briefings match that search" : "No briefings right now",
      query ? "Try a broader term or switch your branch." : "Refresh to pull the latest engineering news. Curated reading is used when feeds are down.",
      `<button class="btn btn-secondary" type="button" data-action="refresh-news">${icon("refresh")}Refresh briefings</button>`
    );
    return;
  }

  grid.innerHTML = filtered.map(newsCard).join("");
}

function renderNewsSource() {
  const container = $("#news-source");
  if (!container) return;
  const meta = state.newsMeta || {};
  const fallback = (state.news || []).some((item) => item.fallback);
  container.className = `source-strip ${fallback ? "curated" : ""}`;
  container.innerHTML = `
    <span class="live-dot"></span>
    <strong>${fallback ? "Curated reading list" : "Live RSS briefing"}</strong>
    <span class="sep">·</span>
    <span>${esc(state.profile.branch)}</span>
    <span class="sep">·</span>
    <span>${meta.ai_mode === "ai" ? `Summarized with ${esc(state.features.model || "Gemini")}` : "Local extractive summaries"}</span>
    <span class="spacer"></span>
    <span>${meta.updated_at ? `Updated ${timeAgo(meta.updated_at)}` : "Just now"}</span>
  `;
}

function newsCard(item) {
  const saved = isSaved("news", item.id);
  const url = safeUrl(item.link);
  const tldr = item.tldr || "";
  const takeawayKey = (value) => String(value || "").toLowerCase().replace(/[^a-z0-9 ]+/g, " ").replace(/\s+/g, " ").trim();
  const tldrKey = takeawayKey(tldr);
  const rawBullets = Array.isArray(item.bullets)
    ? item.bullets
    : String(item.summary || "").split(/\n+/).filter(Boolean);
  const bullets = rawBullets
    .filter((bullet) => {
      const key = takeawayKey(bullet);
      return key && key !== tldrKey && !tldrKey.includes(key);
    })
    .slice(0, 3);
  return `
    <article class="news-card" data-id="${esc(item.id)}">
      <div class="news-meta">
        <span class="news-source">${esc(item.source || "Engineering publisher")}</span>
        <span class="news-date">${item.published_at ? esc(timeAgo(item.published_at)) : ""}</span>
        ${item.fallback ? `<span class="pill pill-gold">${icon("book")}Curated</span>` : ""}
        ${!tldr && !bullets.length ? `<span class="pill pill-soft">Headline only</span>` : ""}
        <span class="spacer"></span>
        <button class="icon-action ${saved ? "active" : ""}" type="button" aria-label="${saved ? "Remove bookmark" : "Save briefing"}" data-action="toggle-save" data-kind="news" data-id="${esc(item.id)}">${icon("bookmark")}</button>
      </div>
      <h3 class="news-title">${url ? `<a href="${esc(url)}" target="_blank" rel="noopener noreferrer">${esc(item.title)}</a>` : esc(item.title)}</h3>
      ${tldr ? `<p class="news-tldr">${esc(tldr)}</p>` : ""}
      ${bullets.length ? `<ul class="news-takeaways">${bullets.map((bullet) => `<li>${esc(bullet)}</li>`).join("")}</ul>` : ""}
      <div class="news-tags">${(item.tags || []).slice(0, 4).map((tag) => `<span class="news-tag">${esc(tag)}</span>`).join("")}</div>
      <div class="news-foot">
        <span class="mode-badge">${icon(item.summary_mode === "ai" ? "sparkles" : "bolt")}${item.summary_mode === "ai" ? "AI brief" : "Local brief"}</span>
        <span class="spacer"></span>
        <button class="icon-action" type="button" title="Save to reading list" aria-label="Save to reading list" data-action="task-from" data-kind="news" data-id="${esc(item.id)}">${icon("tasks")}</button>
        ${url ? `<a class="icon-action" href="${esc(url)}" target="_blank" rel="noopener noreferrer" title="Read original" aria-label="Read original">${icon("external")}</a>` : ""}
      </div>
    </article>`;
}

/* --------------------------------------------------------------------------
   Saved
   -------------------------------------------------------------------------- */

function renderSaved() {
  const grid = $("#saved-grid");
  if (!grid) return;
  const tabs = $("#saved-tabs");
  const types = ["All", ...Array.from(new Set((state.bookmarks || []).map((item) => item.type)))];
  if (tabs) {
    tabs.innerHTML = types
      .map(
        (type) => `
        <button class="chip ${state.filters.savedType === type ? "active" : ""}" type="button" data-action="filter-saved-type" data-value="${esc(type)}">
          ${esc(type === "All" ? "Everything" : type.charAt(0).toUpperCase() + type.slice(1))}
          <span class="count">${type === "All" ? state.bookmarks.length : state.bookmarks.filter((item) => item.type === type).length}</span>
        </button>`
      )
      .join("");
  }

  const filtered = (state.bookmarks || []).filter(
    (item) => state.filters.savedType === "All" || item.type === state.filters.savedType
  );

  if (!filtered.length) {
    grid.innerHTML = emptyState(
      "bookmark",
      state.bookmarks.length ? "Nothing in this collection" : "Your library is empty",
      state.bookmarks.length
        ? "Switch the filter to see everything you have saved."
        : "Tap the bookmark icon on any campus update, opportunity or briefing and it will land here.",
      `<a class="btn btn-primary" href="#opportunities">${icon("trophy")}Explore opportunities</a>`
    );
    return;
  }

  grid.innerHTML = filtered
    .map((bookmark) => {
      const iconName = bookmark.type === "news" ? "news" : bookmark.type === "opportunity" ? "trophy" : "campus";
      const url = safeUrl(bookmark.url);
      return `
        <article class="saved-card" data-id="${esc(bookmark.id)}">
          <span class="saved-icon ${esc(bookmark.type)}">${icon(iconName)}</span>
          <div class="saved-copy">
            <strong>${url ? `<a href="${esc(url)}" target="_blank" rel="noopener noreferrer">${esc(bookmark.title)}</a>` : esc(bookmark.title)}</strong>
            <p>${esc(bookmark.subtitle || "")}</p>
            <div class="saved-foot">
              <span class="pill pill-soft">${esc(bookmark.type)}</span>
              <small class="muted" style="font-size:10px">${esc(fmtDateTime(bookmark.created_at))}</small>
              <span class="spacer"></span>
              <button class="icon-action" type="button" aria-label="Remove bookmark" data-action="delete-bookmark" data-id="${esc(bookmark.id)}">${icon("trash")}</button>
            </div>
          </div>
        </article>`;
    })
    .join("");
}
