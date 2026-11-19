"use strict";

/* ==========================================================================
   STUDENT ECOSYSTEM — TOOLS
   Mail summarizer, academic vault, task hub, settings and action handling.
   ========================================================================== */

/* --------------------------------------------------------------------------
   Shared confirm dialog
   -------------------------------------------------------------------------- */

function confirmAction({ title, message, confirmLabel = "Delete", onConfirm }) {
  openModal({
    eyebrow: "Please confirm",
    title,
    body: `<p style="font-size:13px;line-height:1.65;color:var(--ink-2)">${esc(message)}</p>`,
    footer: `
      <span class="spacer"></span>
      <button class="btn btn-ghost" type="button" data-close-modal>Cancel</button>
      <button class="btn btn-danger" type="button" id="confirm-action">${esc(confirmLabel)}</button>`,
    onMount() {
      $("#confirm-action")?.addEventListener("click", async () => {
        const button = $("#confirm-action");
        if (button) {
          button.disabled = true;
          button.textContent = "Working…";
        }
        try {
          await onConfirm();
          closeModal();
        } catch (error) {
          toast(error.message, { type: "error", title: "Action failed" });
          if (button) {
            button.disabled = false;
            button.textContent = confirmLabel;
          }
        }
      });
    },
  });
}

/* --------------------------------------------------------------------------
   Task helpers
   -------------------------------------------------------------------------- */

async function createTask(payload) {
  const response = await api("/api/tasks", { method: "POST", body: payload });
  if (response.stats) state.stats = response.stats;
  await fetchTasks(true);
  updateBadges();
  rerenderActiveView();
  if (currentView() === "overview") renderOverview();
  return response.task;
}

async function updateTaskStatus(id, status) {
  const response = await api(`/api/tasks/${encodeURIComponent(id)}`, {
    method: "PATCH",
    body: { status },
  });
  if (response.stats) state.stats = response.stats;
  await fetchTasks(true);
  updateBadges();
  renderTasks();
  if (currentView() === "overview") renderOverview();
  return response.task;
}

function taskPrefill(kind, item) {
  if (!item) return { title: "New task" };
  if (kind === "campus") {
    const action = (item.what_to_do || [])[0] || `Review: ${item.title}`;
    return {
      title: action,
      notes: [item.tldr, item.link].filter(Boolean).join("\n\n"),
      due_date: item.deadline || "",
      priority: ["high", "urgent"].includes(item.urgency) ? "high" : "medium",
      tags: ["mit-wpu", item.category ? String(item.category).toLowerCase() : "campus"],
      source_type: "campus",
      source_id: item.id || "",
    };
  }
  if (kind === "opportunity") {
    const days = daysUntil(item.deadline);
    return {
      title: `Apply: ${item.title}`,
      notes: [item.why, item.url].filter(Boolean).join("\n\n"),
      due_date: item.deadline || "",
      priority: days !== null && days <= 7 ? "urgent" : days !== null && days <= 21 ? "high" : "medium",
      tags: [item.track ? String(item.track).toLowerCase() : "opportunity", item.mode || ""].filter(Boolean),
      source_type: "opportunity",
      source_id: item.id || "",
    };
  }
  if (kind === "news") {
    return {
      title: `Read: ${truncate(item.title, 120)}`,
      notes: [item.tldr, item.link].filter(Boolean).join("\n\n"),
      due_date: "",
      priority: "low",
      tags: ["reading", ...(item.tags || []).slice(0, 2)],
      source_type: "news",
      source_id: item.id || "",
    };
  }
  if (kind === "summary") {
    return {
      title: (item.action_items || [])[0] || `Follow up: ${item.subject}`,
      notes: item.tldr || "",
      due_date: (item.deadlines || [])[0]?.date || "",
      priority: ["high", "urgent"].includes(item.urgency) ? "high" : "medium",
      tags: ["mail", ...(item.tags || []).slice(0, 2)],
      source_type: "summary",
      source_id: item.id || "",
    };
  }
  return { title: item.title || "New task" };
}

function openTaskModal(task = null, prefill = {}) {
  const data = task || prefill;
  const editing = Boolean(task);
  const tags = Array.isArray(data.tags) ? data.tags.join(", ") : data.tags || "";
  const body = `
    <form id="task-form" class="settings-form">
      <label class="field">
        <span>Task title</span>
        <input name="title" type="text" required maxlength="300" value="${esc(data.title || "")}" placeholder="e.g. Submit DBMS assignment" autocomplete="off">
      </label>
      <label class="field">
        <span>Notes <em>optional</em></span>
        <textarea name="notes" rows="3" maxlength="4000" placeholder="Context, links or the next concrete step…">${esc(data.notes || "")}</textarea>
      </label>
      <div class="field-row">
        <label class="field"><span>Due date</span><input name="due_date" type="date" value="${esc(data.due_date || "")}"></label>
        <label class="field">
          <span>Priority</span>
          <select name="priority">
            ${["urgent", "high", "medium", "low"].map((value) => `<option value="${value}" ${((data.priority || "medium") === value) ? "selected" : ""}>${value.charAt(0).toUpperCase() + value.slice(1)}</option>`).join("")}
          </select>
        </label>
      </div>
      <div class="field-row">
        <label class="field">
          <span>Status</span>
          <select name="status">
            <option value="todo" ${(data.status || "todo") === "todo" ? "selected" : ""}>To do</option>
            <option value="doing" ${data.status === "doing" ? "selected" : ""}>In progress</option>
            <option value="done" ${data.status === "done" ? "selected" : ""}>Done</option>
          </select>
        </label>
        <label class="field"><span>Tags <em>comma separated</em></span><input name="tags" type="text" value="${esc(tags)}" placeholder="exams, placement"></label>
      </div>
    </form>`;

  const footer = `
    ${editing ? `<button class="btn btn-danger btn-sm" type="button" id="task-modal-delete">${icon("trash")}Delete</button>` : ""}
    <span class="spacer"></span>
    <button class="btn btn-ghost" type="button" data-close-modal>Cancel</button>
    <button class="btn btn-primary" type="submit" form="task-form">${editing ? "Save changes" : "Add task"}</button>`;

  openModal({
    eyebrow: editing ? "Edit task" : "Task hub",
    title: editing ? "Update task" : "Capture a task",
    body,
    footer,
    onMount() {
      $("#task-form")?.addEventListener("submit", async (event) => {
        event.preventDefault();
        const form = event.currentTarget;
        const formData = new FormData(form);
        const payload = {
          title: String(formData.get("title") || "").trim(),
          notes: String(formData.get("notes") || "").trim(),
          due_date: String(formData.get("due_date") || ""),
          priority: String(formData.get("priority") || "medium"),
          status: String(formData.get("status") || "todo"),
          tags: String(formData.get("tags") || "")
            .split(",")
            .map((tag) => tag.trim())
            .filter(Boolean),
        };
        if (!payload.title) {
          toast("Give the task a title first.", { type: "error", title: "Missing title" });
          return;
        }
        const submit = $('button[type="submit"][form="task-form"]');
        if (submit) {
          submit.disabled = true;
          submit.textContent = "Saving…";
        }
        try {
          if (editing) {
            await api(`/api/tasks/${encodeURIComponent(task.id)}`, { method: "PATCH", body: payload });
            toast("Task updated.", { title: "Saved" });
          } else {
            await createTask({ ...payload, source_type: data.source_type || "manual", source_id: data.source_id || "" });
            toast("Added to your task hub.", { title: "Task created" });
          }
          await fetchTasks(true);
          updateBadges();
          closeModal();
          if (currentView() === "tasks") renderTasks();
          if (currentView() === "overview") renderOverview();
        } catch (error) {
          toast(error.message, { type: "error", title: "Could not save task" });
          if (submit) {
            submit.disabled = false;
            submit.textContent = editing ? "Save changes" : "Add task";
          }
        }
      });

      $("#task-modal-delete")?.addEventListener("click", () => {
        confirmAction({
          title: "Delete this task?",
          message: "This permanently removes the task from your hub.",
          onConfirm: async () => {
            await api(`/api/tasks/${encodeURIComponent(task.id)}`, { method: "DELETE" });
            await fetchTasks(true);
            updateBadges();
            renderTasks();
            renderOverview();
            toast("Task deleted.", { title: "Removed", type: "info" });
          },
        });
      });
    },
  });
}

/* --------------------------------------------------------------------------
   Tasks view
   -------------------------------------------------------------------------- */

async function loadTasksView(force = false) {
  if (!state.loaded.tasks || force) {
    const board = $("#task-board");
    if (board) board.innerHTML = skeletonCards(3);
    await fetchTasks(force);
  }
  renderTasks();
}

function filteredTasks() {
  const query = state.filters.taskQuery.trim().toLowerCase();
  const priority = state.filters.taskPriority;
  return (state.tasks || []).filter((task) => {
    if (priority !== "All" && task.priority !== priority) return false;
    if (!query) return true;
    return `${task.title} ${task.notes} ${(task.tags || []).join(" ")}`.toLowerCase().includes(query);
  });
}

function renderTasks() {
  const board = $("#task-board");
  if (!board) return;
  const tasks = filteredTasks();
  const statuses = [
    { key: "todo", label: "To do" },
    { key: "doing", label: "In progress" },
    { key: "done", label: "Done" },
  ];

  board.innerHTML = statuses
    .map((status) => {
      const columnTasks = tasks.filter((task) => task.status === status.key);
      return `
        <section class="kanban-col" data-status="${status.key}">
          <div class="kanban-head">
            <strong><span class="kanban-dot"></span>${status.label}</strong>
            <span class="kanban-count">${columnTasks.length}</span>
            <span class="spacer"></span>
            <button class="icon-btn" type="button" aria-label="Add task to ${status.label}" data-action="task-add-status" data-value="${status.key}">${icon("plus")}</button>
          </div>
          <div class="kanban-list" data-status="${status.key}">
            ${columnTasks.length ? columnTasks.map(taskCard).join("") : `<div class="kanban-empty">${status.key === "done" ? "Completed tasks land here." : "Nothing here. Add a task or drag one over."}</div>`}
          </div>
        </section>`;
    })
    .join("");

  const summary = $("#task-summary");
  if (summary) {
    const overdue = tasks.filter((task) => task.overdue).length;
    summary.innerHTML = `
      <span><strong>${state.stats.tasks_open || 0}</strong> open</span>
      <span><strong>${state.stats.due_week || 0}</strong> due this week</span>
      <span><strong style="${overdue ? "color:var(--danger)" : ""}">${overdue}</strong> overdue</span>`;
  }
  initTaskDnD();
}

function taskCard(task) {
  const due = task.due_date ? deadlineLabel(task.due_date) : null;
  const isSoon = task.due_date && daysUntil(task.due_date) !== null && daysUntil(task.due_date) <= 2;
  const tags = (task.tags || []).slice(0, 3);
  return `
    <article class="task-card ${task.status === "done" ? "done" : ""}" draggable="true" data-task-id="${esc(task.id)}">
      <div class="task-card-top">
        <button class="task-check" type="button" aria-label="Toggle task complete" data-action="task-toggle" data-id="${esc(task.id)}">
          ${icon("check")}
        </button>
        <span class="task-title">${esc(task.title)}</span>
        <span class="priority-dot ${esc(task.priority || "medium")}" title="${esc(task.priority || "medium")} priority"></span>
        <button class="task-menu-btn" type="button" aria-label="Edit task" data-action="task-edit" data-id="${esc(task.id)}">${icon("edit")}</button>
      </div>
      ${task.notes ? `<p class="task-notes">${esc(task.notes)}</p>` : ""}
      ${tags.length ? `<div class="task-tags">${tags.map((tag) => `<span class="task-tag">${esc(tag)}</span>`).join("")}</div>` : ""}
      <div class="task-card-foot">
        ${due ? `<span class="task-due ${isSoon ? "soon" : ""}">${icon("clock")}${esc(due.text)}</span>` : `<span class="task-due">${icon("clock")}No date</span>`}
        <span class="spacer"></span>
        <button class="task-menu-btn" type="button" aria-label="Delete task" data-action="task-delete" data-id="${esc(task.id)}">${icon("trash")}</button>
      </div>
    </article>`;
}

function initTaskDnD() {
  $$(".task-card").forEach((card) => {
    card.addEventListener("dragstart", (event) => {
      card.classList.add("dragging");
      event.dataTransfer.setData("text/plain", card.dataset.taskId);
      event.dataTransfer.effectAllowed = "move";
    });
    card.addEventListener("dragend", () => card.classList.remove("dragging"));
  });

  $$(".kanban-col").forEach((column) => {
    column.addEventListener("dragover", (event) => {
      event.preventDefault();
      column.classList.add("dragover");
    });
    column.addEventListener("dragleave", (event) => {
      if (!column.contains(event.relatedTarget)) column.classList.remove("dragover");
    });
    column.addEventListener("drop", async (event) => {
      event.preventDefault();
      column.classList.remove("dragover");
      const id = event.dataTransfer.getData("text/plain");
      const status = column.dataset.status;
      if (!id || !status) return;
      try {
        await updateTaskStatus(id, status);
        toast(`Moved to ${status === "doing" ? "in progress" : status === "done" ? "done" : "to do"}.`, { title: "Task updated" });
      } catch (error) {
        toast(error.message, { type: "error", title: "Could not move task" });
      }
    });
  });
}

/* --------------------------------------------------------------------------
   Academic vault
   -------------------------------------------------------------------------- */

async function loadVaultView(force = false) {
  if (!state.loaded.vault || force) {
    const grid = $("#vault-grid");
    if (grid) grid.innerHTML = skeletonCards(6);
    await fetchVault(force);
  }
  renderVault();
}

function renderVault() {
  const grid = $("#vault-grid");
  if (!grid) return;
  const query = state.filters.vaultQuery.trim().toLowerCase();
  const scope = state.filters.vaultScope;

  const filtered = (state.vault || []).filter((item) => {
    if (state.filters.vaultSubject !== "All" && item.subject !== state.filters.vaultSubject) return false;
    if (state.filters.vaultType !== "All" && item.type !== state.filters.vaultType) return false;
    if (scope === "mine" && item.branch !== "All" && item.branch !== state.profile.branch) return false;
    if (scope === "starred" && !item.starred) return false;
    if (!query) return true;
    const haystack = `${item.title} ${item.description} ${item.subject} ${item.branch} ${(item.tags || []).join(" ")}`.toLowerCase();
    return haystack.includes(query);
  });

  renderVaultSubjects();

  const typeSelect = $("#vault-type");
  if (typeSelect && typeSelect.options.length <= 1) {
    typeSelect.innerHTML =
      `<option value="All">All types</option>` +
      (state.vaultTypes || []).map((type) => `<option value="${esc(type)}">${esc(type.charAt(0).toUpperCase() + type.slice(1))}</option>`).join("");
  }

  if (!filtered.length) {
    grid.innerHTML = emptyState(
      "book",
      "No resources match",
      query || scope !== "All" || state.filters.vaultSubject !== "All"
        ? "Try another subject, type or scope."
        : "Add your first resource to start building your vault.",
      `<button class="btn btn-primary" type="button" data-action="vault-add">${icon("plus")}Add resource</button>`
    );
    return;
  }

  grid.innerHTML = filtered.map(vaultCard).join("");
}

function renderVaultSubjects() {
  const container = $("#vault-subjects");
  if (!container) return;
  const counts = {};
  (state.vault || []).forEach((item) => {
    counts[item.subject] = (counts[item.subject] || 0) + 1;
  });
  const subjects = ["All", ...Object.keys(counts).sort((a, b) => counts[b] - counts[a])];
  container.innerHTML = subjects
    .map(
      (subject) => `
      <button class="chip ${state.filters.vaultSubject === subject ? "active" : ""}" type="button" data-action="filter-vault-subject" data-value="${esc(subject)}">
        ${esc(subject)} <span class="count">${subject === "All" ? state.vault.length : counts[subject]}</span>
      </button>`
    )
    .join("");
}

function vaultCard(item) {
  const url = safeUrl(item.url);
  const typeIcon = TYPE_ICONS[item.type] || "link";
  return `
    <article class="vault-card ${item.starred ? "starred" : ""}" data-id="${esc(item.id)}">
      <div class="vault-top">
        <span class="vault-type-icon ${esc(item.type)}">${icon(typeIcon)}</span>
        <span class="pill pill-soft">${esc(item.type)}</span>
        <span class="spacer"></span>
        <button class="icon-action ${item.starred ? "active" : ""}" type="button" aria-label="${item.starred ? "Unstar" : "Star"} resource" data-action="toggle-star" data-id="${esc(item.id)}">${icon("star")}</button>
      </div>
      <h3>${url ? `<a href="${esc(url)}" target="_blank" rel="noopener noreferrer">${esc(item.title)}</a>` : esc(item.title)}</h3>
      <p>${esc(item.description || "No description yet.")}</p>
      <div class="vault-meta">
        <span class="vault-subject">${esc(item.subject)}</span>
        <span class="vault-branch">${icon("grad")}${esc(item.branch)}</span>
      </div>
      <div class="vault-foot">
        ${url ? `<a class="open-link" href="${esc(url)}" target="_blank" rel="noopener noreferrer">Open ${icon("external")}</a>` : `<span class="muted" style="font-size:10.5px">No link</span>`}
        <span class="spacer"></span>
        <button class="icon-action" type="button" aria-label="Edit resource" data-action="edit-resource" data-id="${esc(item.id)}">${icon("edit")}</button>
        <button class="icon-action" type="button" aria-label="Delete resource" data-action="delete-resource" data-id="${esc(item.id)}">${icon("trash")}</button>
      </div>
    </article>`;
}

function openVaultModal(resource = null) {
  const editing = Boolean(resource);
  const branches = ["All", ...(state.branches || [])];
  const types = ["course", "notes", "video", "practice", "tool", "reference", "link"];
  const body = `
    <form id="vault-form" class="settings-form">
      <label class="field"><span>Title</span><input name="title" type="text" required maxlength="300" value="${esc(resource?.title || "")}" placeholder="e.g. NPTEL — Operating Systems"></label>
      <div class="field-row">
        <label class="field"><span>Subject</span><input name="subject" type="text" maxlength="80" value="${esc(resource?.subject || "")}" placeholder="e.g. Operating Systems" list="vault-subject-list">
          <datalist id="vault-subject-list">${(state.vaultSubjects || []).map((subject) => `<option value="${esc(subject)}"></option>`).join("")}</datalist>
        </label>
        <label class="field"><span>Branch</span><select name="branch">${branches.map((branch) => `<option value="${esc(branch)}" ${(resource?.branch || "All") === branch ? "selected" : ""}>${esc(branch)}</option>`).join("")}</select></label>
      </div>
      <div class="field-row">
        <label class="field"><span>Type</span><select name="type">${types.map((type) => `<option value="${type}" ${(resource?.type || "link") === type ? "selected" : ""}>${type.charAt(0).toUpperCase() + type.slice(1)}</option>`).join("")}</select></label>
        <label class="field"><span>Tags <em>comma separated</em></span><input name="tags" type="text" value="${esc((resource?.tags || []).join(", "))}" placeholder="dsa, semester 5"></label>
      </div>
      <label class="field"><span>URL</span><input name="url" type="url" maxlength="1200" value="${esc(resource?.url || "")}" placeholder="https://…"></label>
      <label class="field"><span>Description</span><textarea name="description" rows="3" maxlength="2000" placeholder="Why is this useful and when will you use it?">${esc(resource?.description || "")}</textarea></label>
      <label class="check-field"><input type="checkbox" name="starred" ${resource?.starred ? "checked" : ""}> Pin to the top of my vault</label>
    </form>`;

  openModal({
    eyebrow: "Academic vault",
    title: editing ? "Edit resource" : "Add a resource",
    body,
    footer: `
      <span class="spacer"></span>
      <button class="btn btn-ghost" type="button" data-close-modal>Cancel</button>
      <button class="btn btn-primary" type="submit" form="vault-form">${editing ? "Save changes" : "Add to vault"}</button>`,
    onMount() {
      $("#vault-form")?.addEventListener("submit", async (event) => {
        event.preventDefault();
        const formData = new FormData(event.currentTarget);
        const payload = {
          title: String(formData.get("title") || "").trim(),
          subject: String(formData.get("subject") || "").trim() || "General",
          branch: String(formData.get("branch") || "All"),
          type: String(formData.get("type") || "link"),
          url: String(formData.get("url") || "").trim(),
          description: String(formData.get("description") || "").trim(),
          tags: String(formData.get("tags") || "").split(",").map((tag) => tag.trim()).filter(Boolean),
          starred: formData.get("starred") === "on",
        };
        if (!payload.title) {
          toast("A title is required.", { type: "error", title: "Missing title" });
          return;
        }
        const submit = $('button[type="submit"][form="vault-form"]');
        if (submit) {
          submit.disabled = true;
          submit.textContent = "Saving…";
        }
        try {
          if (editing) {
            await api(`/api/vault/${encodeURIComponent(resource.id)}`, { method: "PATCH", body: payload });
            toast("Resource updated.", { title: "Saved" });
          } else {
            await api("/api/vault", { method: "POST", body: payload });
            toast("Added to your academic vault.", { title: "Resource created" });
          }
          await fetchVault(true);
          closeModal();
          renderVault();
        } catch (error) {
          toast(error.message, { type: "error", title: "Could not save resource" });
          if (submit) {
            submit.disabled = false;
            submit.textContent = editing ? "Save changes" : "Add to vault";
          }
        }
      });
    },
  });
}

/* --------------------------------------------------------------------------
   Mail summarizer
   -------------------------------------------------------------------------- */

async function loadMailView(force = false) {
  if (!state.loaded.mail || force) {
    const history = $("#mail-history");
    if (history) history.innerHTML = skeletonRows(4);
    await fetchSummaries(force);
  }
  renderMailHistory();
  if (state.currentSummary) renderSummaryResult(state.currentSummary);
}

function renderMailHistory() {
  const container = $("#mail-history");
  if (!container) return;
  const count = $("#mail-history-count");
  if (count) count.textContent = String((state.summaries || []).length);
  if (!state.summaries || !state.summaries.length) {
    container.innerHTML = `<div class="empty-state compact"><div class="empty-icon">${icon("inbox")}</div><h3>No notices yet</h3><p>Summarize your first email and it will be saved here for later.</p></div>`;
    return;
  }
  container.innerHTML = state.summaries
    .map(
      (summary) => `
      <article class="history-item" data-action="open-summary" data-id="${esc(summary.id)}">
        <div class="history-item-top">
          <span class="pill pill-primary">${esc(summary.category || "General")}</span>
          <span class="pill ${urgencyClass(summary.urgency)}">${esc(urgencyLabel(summary.urgency))}</span>
          ${summary.mode === "ai" ? `<span class="pill pill-mint">${icon("sparkles")}AI</span>` : ""}
        </div>
        <h4>${esc(summary.subject || "Untitled notice")}</h4>
        <p>${esc(summary.tldr || "No TL;DR available.")}</p>
        <div class="history-item-foot">
          <small>${esc(timeAgo(summary.created_at))}</small>
          <div style="display:flex;gap:4px">
            <button class="icon-action" type="button" aria-label="Convert to task" data-action="summary-task" data-id="${esc(summary.id)}">${icon("calendar")}</button>
            <button class="icon-action" type="button" aria-label="Delete summary" data-action="delete-summary" data-id="${esc(summary.id)}">${icon("trash")}</button>
          </div>
        </div>
      </article>`
    )
    .join("");
}

function renderSummaryResult(summary) {
  if (!summary) return;
  const container = $("#mail-result");
  if (!container) return;
  const deadlines = summary.deadlines || [];
  const actions = summary.action_items || [];
  const tags = summary.tags || [];
  const modeLabel = summary.mode === "ai" ? "Gemini summary" : "Smart local summary";

  container.innerHTML = `
    <article class="summary-result-card">
      <div class="summary-head">
        <h3>${esc(summary.subject || "Notice summary")}</h3>
        <span class="pill pill-primary">${esc(summary.category || "General")}</span>
        <span class="pill ${urgencyClass(summary.urgency)}">${esc(urgencyLabel(summary.urgency))}</span>
        <span class="mode-badge">${icon(summary.mode === "ai" ? "sparkles" : "bolt")}${esc(modeLabel)}</span>
        <span class="spacer"></span>
        <span class="muted" style="font-size:10px">${esc(fmtDateTime(summary.created_at || new Date().toISOString()))}</span>
      </div>
      <div class="summary-body">
        <div>
          <div class="summary-section-label">${icon("sparkles")}TL;DR</div>
          <p class="summary-tldr">${esc(summary.tldr || "No summary available.")}</p>
        </div>
        ${deadlines.length ? `
          <div>
            <div class="summary-section-label">${icon("clock")}Dates &amp; deadlines</div>
            <div class="summary-deadlines">
              ${deadlines.map((deadline) => {
                const info = deadlineLabel(deadline.date);
                return `<div class="summary-deadline">${icon("calendar")}<div><strong>${esc(deadline.label || "Deadline")}</strong><small>${esc(deadline.date ? fmtDate(deadline.date) : "No date stated")}</small></div><span class="days">${esc(info.text)}</span></div>`;
              }).join("")}
            </div>
          </div>` : ""}
        ${actions.length ? `
          <div>
            <div class="summary-section-label">${icon("check")}Action items</div>
            ${actions.slice(0, 4).map((action, index) => `
              <div class="summary-actions">
                <button class="check-box" type="button" title="Convert to task" aria-label="Convert to task" data-action="summary-action-task" data-index="${index}">${icon("check")}</button>
                <span>${esc(action)}</span>
              </div>`).join("")}
          </div>` : ""}
        ${tags.length ? `<div class="news-tags">${tags.map((tag) => `<span class="news-tag">#${esc(tag)}</span>`).join("")}</div>` : ""}
      </div>
      <div class="summary-foot">
        <button class="btn btn-primary btn-sm" type="button" data-action="summary-task" data-id="${esc(summary.id)}">${icon("plus")}Create task</button>
        <button class="btn btn-secondary btn-sm" type="button" data-action="copy-summary" data-id="${esc(summary.id)}">${icon("copy")}Copy</button>
        <span class="spacer"></span>
        <button class="btn btn-ghost btn-sm" type="button" data-action="delete-summary" data-id="${esc(summary.id)}">${icon("trash")}Delete</button>
      </div>
    </article>`;
}

async function openSummaryById(id) {
  let summary = state.summaries.find((item) => String(item.id) === String(id));
  if (!summary) {
    try {
      await fetchSummaries(true);
      summary = state.summaries.find((item) => String(item.id) === String(id));
    } catch {
      summary = null;
    }
  }
  if (!summary) {
    toast("That summary could not be found.", { type: "error", title: "Not found" });
    return;
  }
  state.currentSummary = summary;
  renderSummaryResult(summary);
  if (currentView() !== "mail") navigate("mail");
  $("#mail-result")?.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

async function handleMailSubmit(event) {
  event.preventDefault();
  const text = ($("#mail-body")?.value || "").trim();
  const subject = ($("#mail-subject")?.value || "").trim();
  const sender = ($("#mail-sender")?.value || "").trim();
  const file = $("#mail-file")?.files?.[0];
  const createTaskChecked = Boolean($("#mail-create-task")?.checked);

  if (text.length < 20 && !file) {
    toast("Paste at least a couple of sentences, or upload a file.", { type: "error", title: "Nothing to summarize" });
    $("#mail-body")?.focus();
    return;
  }

  const result = $("#mail-result");
  const submit = $("#mail-submit");
  if (result) result.innerHTML = skeletonPanel("Reading the notice and extracting actions");
  if (submit) {
    submit.disabled = true;
    submit.innerHTML = `${icon("refresh", "spin")}Summarizing…`;
  }

  try {
    let response;
    if (file) {
      const formData = new FormData();
      formData.append("file", file);
      if (text) formData.append("text", text);
      formData.append("subject", subject);
      formData.append("sender", sender);
      formData.append("create_task", createTaskChecked ? "true" : "false");
      response = await api("/api/summarize", { method: "POST", formData, timeout: 90000 });
    } else {
      response = await api("/api/summarize", {
        method: "POST",
        body: { text, subject, sender, create_task: createTaskChecked },
        timeout: 90000,
      });
    }
    const summary = response.summary;
    state.currentSummary = summary;
    state.summaries.unshift(summary);
    renderSummaryResult(summary);
    renderMailHistory();
    if (response.stats) state.stats = response.stats;
    if (response.task) {
      await fetchTasks(true);
      updateBadges();
      toast("Notice summarized and the top action was added to your tasks.", { title: "Done" });
    } else {
      toast(
        summary.mode === "ai" ? "Gemini extracted the key details." : "Generated with the local fallback summarizer.",
        { title: "Notice summarized" }
      );
    }
    const fileInput = $("#mail-file");
    if (fileInput) fileInput.value = "";
    const fileName = $("#mail-file-name");
    if (fileName) fileName.hidden = true;
  } catch (error) {
    if (result) {
      result.innerHTML = `
        <div class="empty-state compact">
          <div class="empty-icon" style="background:var(--danger-soft);color:var(--danger)">${icon("alert")}</div>
          <h3>We couldn't summarize that</h3>
          <p>${esc(error.message || "The summarizer is unavailable right now.")}</p>
          <button class="btn btn-secondary btn-sm" type="button" data-action="retry-mail">${icon("refresh")}Try again</button>
        </div>`;
    }
    toast(error.message, { type: "error", title: "Summarizer error" });
  } finally {
    if (submit) {
      submit.disabled = false;
      submit.innerHTML = `${icon("sparkles")}Summarize notice`;
    }
  }
}

function sampleNotice() {
  const date = new Date();
  date.setDate(date.getDate() + 12);
  const deadline = date.toLocaleDateString("en-GB", { day: "numeric", month: "long", year: "numeric" });
  const subject = "End-semester examination timetable and hall ticket instructions";
  const sender = "examination@mitwpu.edu.in";
  const text = `Dear students,

The end-semester examination timetable for Semester 5 has been published on the student portal. Please verify your registered subjects and report any discrepancy to the examination cell by ${deadline}.

Hall tickets will be available for download from the portal three days before the first examination. Students with pending fee dues or attendance shortages will not be issued a hall ticket.

You must carry your MIT-WPU identity card and a printed hall ticket to every examination. Electronic devices, including smart watches, are not permitted in the examination hall.

For assistance, contact the examination cell between 10:00 AM and 4:00 PM on working days.

Regards,
Examination Cell
MIT World Peace University, Pune`;

  const subjectInput = $("#mail-subject");
  const senderInput = $("#mail-sender");
  const bodyInput = $("#mail-body");
  if (subjectInput) subjectInput.value = subject;
  if (senderInput) senderInput.value = sender;
  if (bodyInput) {
    bodyInput.value = text;
    bodyInput.focus();
  }
  toast("Sample notice loaded. Press Summarize to see it work.", { title: "Ready", type: "info" });
}

/* --------------------------------------------------------------------------
   Settings
   -------------------------------------------------------------------------- */

function renderSettings() {
  const name = $("#settings-name");
  const branch = $("#settings-branch");
  const year = $("#settings-year");
  const semester = $("#settings-semester");
  const goal = $("#settings-goal");

  if (name) name.value = state.profile.name || "";
  if (year) year.value = state.profile.year || "";
  if (semester) semester.value = state.profile.semester || "";
  if (goal) goal.value = state.profile.goal || "";
  if (branch) {
    branch.innerHTML = (state.branches || []).map((item) => `<option value="${esc(item)}" ${item === state.profile.branch ? "selected" : ""}>${esc(item)}</option>`).join("");
  }

  const status = $("#settings-status");
  if (status) {
    const stats = state.stats || {};
    status.innerHTML = `
      <div class="status-row">${icon("sparkles")}<span>AI summaries</span><strong class="${state.features.ai ? "ok" : "warn"}">${state.features.ai ? "Gemini live" : "Local fallback"}</strong></div>
      <div class="status-row">${icon("layers")}<span>Model</span><strong class="${state.features.ai ? "ok" : "off"}">${esc(state.features.model || "Not configured")}</strong></div>
      <div class="status-row">${icon("campus")}<span>Campus feed</span><strong class="${state.campusStatus?.mode === "live" ? "ok" : "warn"}">${state.campusStatus?.mode === "live" ? "Live scan" : "Curated guide"}</strong></div>
      <div class="status-row">${icon("book")}<span>Local database</span><strong class="ok">SQLite ready</strong></div>
      <div class="status-row">${icon("tasks")}<span>Tasks &amp; summaries</span><strong class="ok">${stats.tasks_open || 0} open · ${stats.summaries || 0} saved</strong></div>
      <div class="status-row">${icon("bookmark")}<span>Bookmarks</span><strong class="ok">${stats.bookmarks || 0} saved</strong></div>`;
  }
}

async function handleSettingsSubmit(event) {
  event.preventDefault();
  const payload = {
    name: ($("#settings-name")?.value || "").trim(),
    branch: $("#settings-branch")?.value || state.profile.branch,
    year: ($("#settings-year")?.value || "").trim(),
    semester: ($("#settings-semester")?.value || "").trim(),
    goal: ($("#settings-goal")?.value || "").trim(),
  };
  const note = $("#settings-note");
  try {
    const response = await api("/api/profile", { method: "PATCH", body: payload });
    const branchChanged = response.profile.branch !== state.profile.branch;
    state.profile = response.profile;
    if (response.stats) state.stats = response.stats;
    updateProfileUI();
    updateBadges();
    if (note) {
      note.textContent = "Saved just now.";
      setTimeout(() => { note.textContent = ""; }, 3000);
    }
    toast("Your preferences are saved.", { title: "Profile updated" });
    if (branchChanged) {
      state.loaded.news = false;
      state.news = [];
      state.newsMeta = null;
      const select = $("#news-branch");
      if (select) select.value = state.profile.branch;
      renderOverview();
    }
    renderSettings();
  } catch (error) {
    toast(error.message, { type: "error", title: "Could not save profile" });
  }
}

/* --------------------------------------------------------------------------
   Actions
   -------------------------------------------------------------------------- */

async function handleAction(action, data, button) {
  const kind = data.kind;
  const id = data.id;

  if (action === "toggle-save") {
    await toggleSave(kind, id);
    return;
  }

  if (action === "task-from") {
    const item = findItem(kind, id);
    if (!item) {
      toast("That item is no longer available.", { type: "error", title: "Not found" });
      return;
    }
    openTaskModal(null, taskPrefill(kind, item));
    return;
  }

  if (action === "refresh-campus") {
    await loadCampusView(true);
    toast("Campus feed refreshed.", { title: "Up to date" });
    return;
  }

  if (action === "refresh-news") {
    await loadNewsView(true);
    toast("Engineering briefings refreshed.", { title: "Up to date" });
    return;
  }

  if (action === "filter-campus-category") {
    state.filters.campusCategory = data.value || "All";
    renderCampus();
    return;
  }

  if (action === "filter-opp-track") {
    state.filters.oppTrack = data.value || "All";
    renderOpportunities();
    return;
  }

  if (action === "toggle-opp-saved") {
    state.filters.oppSaved = !state.filters.oppSaved;
    renderOpportunities();
    return;
  }

  if (action === "reset-opp-filters") {
    state.filters.oppTrack = "All";
    state.filters.oppMode = "All";
    state.filters.oppDeadline = "";
    state.filters.oppQuery = "";
    state.filters.oppSaved = false;
    const search = $("#opp-search");
    if (search) search.value = "";
    const mode = $("#opp-mode");
    if (mode) mode.value = "All";
    const deadline = $("#opp-deadline");
    if (deadline) deadline.value = "";
    renderOpportunities();
    return;
  }

  if (action === "filter-saved-type") {
    state.filters.savedType = data.value || "All";
    renderSaved();
    return;
  }

  if (action === "delete-bookmark") {
    confirmAction({
      title: "Remove this bookmark?",
      message: "You can always save it again from the feed.",
      onConfirm: async () => {
        await api(`/api/bookmarks/${encodeURIComponent(id)}`, { method: "DELETE" });
        await loadSaved(true);
        toast("Bookmark removed.", { title: "Removed", type: "info" });
        rerenderActiveView();
      },
    });
    return;
  }

  if (action === "open-summary") {
    await openSummaryById(id);
    return;
  }

  if (action === "delete-summary") {
    confirmAction({
      title: "Delete this summary?",
      message: "The saved TL;DR, deadlines and action items will be permanently removed.",
      onConfirm: async () => {
        await api(`/api/summaries/${encodeURIComponent(id)}`, { method: "DELETE" });
        state.summaries = state.summaries.filter((item) => String(item.id) !== String(id));
        if (state.currentSummary && String(state.currentSummary.id) === String(id)) {
          state.currentSummary = null;
          const container = $("#mail-result");
          if (container) {
            container.innerHTML = `<div class="empty-state compact"><div class="empty-icon">${icon("mail")}</div><h3>Your summary will appear here</h3><p>TL;DR, deadlines, action items and a category — structured, scannable and saved to your history.</p></div>`;
          }
        }
        renderMailHistory();
        toast("Summary deleted.", { title: "Removed", type: "info" });
      },
    });
    return;
  }

  if (action === "summary-task") {
    const summary = state.summaries.find((item) => String(item.id) === String(id)) || state.currentSummary;
    if (!summary) return;
    openTaskModal(null, taskPrefill("summary", summary));
    return;
  }

  if (action === "summary-action-task") {
    const summary = state.currentSummary;
    if (!summary) return;
    const index = Number(data.index || 0);
    const title = (summary.action_items || [])[index] || summary.tldr;
    openTaskModal(null, {
      ...taskPrefill("summary", summary),
      title,
    });
    return;
  }

  if (action === "copy-summary") {
    const summary = state.summaries.find((item) => String(item.id) === String(id)) || state.currentSummary;
    if (!summary) return;
    const text = composeSummaryText(summary);
    try {
      await navigator.clipboard.writeText(text);
      toast("Summary copied to your clipboard.", { title: "Copied" });
    } catch {
      toast("Your browser blocked clipboard access.", { type: "error", title: "Copy failed" });
    }
    return;
  }

  if (action === "retry-mail") {
    $("#mail-form")?.requestSubmit();
    return;
  }

  if (action === "toggle-star") {
    const resource = state.vault.find((item) => String(item.id) === String(id));
    if (!resource) return;
    try {
      const response = await api(`/api/vault/${encodeURIComponent(id)}`, {
        method: "PATCH",
        body: { starred: !resource.starred },
      });
      const index = state.vault.findIndex((item) => String(item.id) === String(id));
      if (index >= 0) state.vault[index] = response.resource;
      renderVault();
      toast(response.resource.starred ? "Pinned to the top of your vault." : "Removed from pinned.", {
        title: response.resource.starred ? "Starred" : "Unstarred",
        type: "info",
      });
    } catch (error) {
      toast(error.message, { type: "error", title: "Could not update resource" });
    }
    return;
  }

  if (action === "edit-resource") {
    const resource = state.vault.find((item) => String(item.id) === String(id));
    if (resource) openVaultModal(resource);
    return;
  }

  if (action === "vault-add") {
    openVaultModal(null);
    return;
  }

  if (action === "delete-resource") {
    confirmAction({
      title: "Delete this resource?",
      message: "It will be removed from your academic vault.",
      onConfirm: async () => {
        await api(`/api/vault/${encodeURIComponent(id)}`, { method: "DELETE" });
        await fetchVault(true);
        renderVault();
        toast("Resource deleted.", { title: "Removed", type: "info" });
      },
    });
    return;
  }

  if (action === "filter-vault-subject") {
    state.filters.vaultSubject = data.value || "All";
    renderVault();
    return;
  }

  if (action === "task-add-status") {
    openTaskModal(null, { status: data.value || "todo", priority: "medium" });
    return;
  }

  if (action === "task-toggle") {
    const task = state.tasks.find((item) => String(item.id) === String(id));
    if (!task) return;
    try {
      await updateTaskStatus(id, task.status === "done" ? "todo" : "done");
      toast(task.status === "done" ? "Task reopened." : "Task completed.", {
        title: task.status === "done" ? "Reopened" : "Nice work",
      });
    } catch (error) {
      toast(error.message, { type: "error", title: "Could not update task" });
    }
    return;
  }

  if (action === "task-edit") {
    const task = state.tasks.find((item) => String(item.id) === String(id));
    if (task) openTaskModal(task);
    return;
  }

  if (action === "task-delete") {
    const task = state.tasks.find((item) => String(item.id) === String(id));
    if (!task) return;
    confirmAction({
      title: "Delete this task?",
      message: `“${task.title}” will be permanently removed.`,
      onConfirm: async () => {
        await api(`/api/tasks/${encodeURIComponent(id)}`, { method: "DELETE" });
        await fetchTasks(true);
        updateBadges();
        renderTasks();
        if (currentView() === "overview") renderOverview();
        toast("Task deleted.", { title: "Removed", type: "info" });
      },
    });
    return;
  }

  if (action === "refresh-briefing") {
    if (button) button.classList.add("spinning");
    try {
      const data = await api("/api/briefing?refresh=true", { timeout: 60000 });
      state.briefing = data.briefing;
      if (data.stats) state.stats = data.stats;
      renderBriefing();
      renderFocusCard();
      toast("Briefing regenerated from your latest tasks and campus feed.", { title: "Fresh briefing" });
    } catch (error) {
      toast(error.message, { type: "error", title: "Could not regenerate" });
    } finally {
      if (button) button.classList.remove("spinning");
    }
  }
}

function composeSummaryText(summary) {
  const lines = [
    summary.subject || "Notice summary",
    "",
    `TL;DR: ${summary.tldr || ""}`,
    `Category: ${summary.category || "General"} · Urgency: ${urgencyLabel(summary.urgency)}`,
  ];
  if (summary.deadlines?.length) {
    lines.push("", "Deadlines:");
    summary.deadlines.forEach((deadline) => {
      lines.push(`- ${deadline.label || "Deadline"}: ${deadline.date || "no date"}`);
    });
  }
  if (summary.action_items?.length) {
    lines.push("", "Action items:");
    summary.action_items.forEach((action) => lines.push(`- ${action}`));
  }
  return lines.join("\n");
}
