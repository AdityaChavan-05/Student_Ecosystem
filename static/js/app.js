"use strict";

/* ==========================================================================
   STUDENT ECOSYSTEM — BOOT & WIRING
   ========================================================================== */

async function boot() {
  initTheme();
  updateClockUI();
  initGlobalShortcuts();
  bindInterface();
  updateProfileUI();
  updateBadges();

  try {
    const data = await api("/api/bootstrap");
    state.profile = data.profile || state.profile;
    state.branches = data.branches || [];
    state.college = data.college || state.college;
    state.features = data.features || state.features;
    state.stats = data.stats || state.stats;
    state.today = data.today || todayISO();

    const branchSelect = $("#news-branch");
    if (branchSelect) {
      branchSelect.innerHTML = state.branches
        .map((branch) => `<option value="${esc(branch)}">${esc(branch)}</option>`)
        .join("");
      branchSelect.value = state.profile.branch;
    }
    const settingsBranch = $("#settings-branch");
    if (settingsBranch) {
      settingsBranch.innerHTML = state.branches
        .map((branch) => `<option value="${esc(branch)}">${esc(branch)}</option>`)
        .join("");
      settingsBranch.value = state.profile.branch;
    }
    updateProfileUI();
    setActiveView(currentView());
  } catch (error) {
    toast(error.message, { type: "error", title: "Could not connect to the server" });
    console.error("Bootstrap failed:", error);
  }

  await loadBookmarks();
  updateBadges();
  await route();

// Automatically analyse Gmail messages every 15 minutes.
let gmailAnalysisRunning = false;

const runAutomaticGmailAnalysis = async () => {
  if (gmailAnalysisRunning || document.visibilityState !== "visible") {
    return;
  }

  gmailAnalysisRunning = true;

  try {
    const result = await api("/api/gmail/analyse", {
      method: "POST",
    });

    console.log(
      `Automatic Gmail analysis: ${result.processed} checked, ${result.failed} failed.`
    );

    if (currentView() === "mail") {
      await loadGmailPriority();
    }
  } catch (error) {
    console.warn("Automatic Gmail analysis unavailable:", error.message);
  } finally {
    gmailAnalysisRunning = false;
  }
};

// Run once when the website starts.
runAutomaticGmailAnalysis();

// Repeat every 15 minutes while the page is visible.
window.setInterval(runAutomaticGmailAnalysis, 15 * 60 * 1000);

  // Warm the opportunity + vault data in the background.
  if (!state.loaded.opportunities) {
    fetchOpportunities().then(() => {
      if (
        currentView() === "opportunities" ||
        currentView() === "overview"
      ) {
        rerenderActiveView();
      }
    }).catch(() => {});
  }

  if (!state.loaded.vault) {
    fetchVault().catch(() => {});
  }
}

function bindInterface() {
  /* Mobile navigation ---------------------------------------------------- */
  $("#menu-btn")?.addEventListener("click", () => {
    const open = document.body.classList.toggle("nav-open");
    $("#menu-btn").setAttribute("aria-expanded", String(open));
  });

  document.addEventListener("click", (event) => {
    if (document.body.classList.contains("nav-open")) {
      const sidebar = $("#sidebar");
      // The menu button itself toggles the drawer, so ignore its own click.
      if (sidebar && !sidebar.contains(event.target) && !event.target.closest("#menu-btn")) {
        document.body.classList.remove("nav-open");
        $("#menu-btn")?.setAttribute("aria-expanded", "false");
      }
    }
  });

  $$("[data-open-settings]").forEach((element) => {
    element.addEventListener("click", () => navigate("settings"));
  });

  /* Palette -------------------------------------------------------------- */
  $("#search-trigger")?.addEventListener("click", openPalette);
  $("#palette-close")?.addEventListener("click", closePalette);
  $("#palette-overlay")?.addEventListener("click", (event) => {
    if (event.target === $("#palette-overlay")) closePalette();
  });
  $("#palette-input")?.addEventListener("input", (event) => {
    const value = event.target.value;
    renderPalette(value, null);
    debouncedPaletteSearch(value);
  });
  $("#palette-results")?.addEventListener("click", (event) => {
    const option = event.target.closest(".palette-item");
    if (option) activatePaletteOption(option);
  });

  /* Modal ---------------------------------------------------------------- */
  $("#modal-close")?.addEventListener("click", closeModal);
  $("#modal-overlay")?.addEventListener("click", (event) => {
    if (event.target === $("#modal-overlay")) closeModal();
  });
  document.addEventListener("click", (event) => {
    if (event.target.closest("[data-close-modal]")) closeModal();
  });

  /* Notifications -------------------------------------------------------- */
  $("#notification-btn")?.addEventListener("click", (event) => {
    event.stopPropagation();
    openNotificationPanel();
  });
  document.addEventListener("click", (event) => {
    const panel = $("#notification-panel");
    if (!panel || panel.hidden) return;
    if (!panel.contains(event.target) && !event.target.closest("#notification-btn")) {
      panel.hidden = true;
    }
  });
  $("#notification-list")?.addEventListener("click", () => {
    closeNotificationPanel();
  });

  /* Global action delegation -------------------------------------------- */
  document.addEventListener("click", (event) => {
    const trigger = event.target.closest("[data-action]");
    if (!trigger) return;
    const action = trigger.dataset.action;
    if (!action) return;
    event.preventDefault();
    handleAction(action, trigger.dataset, trigger).catch((error) => {
      console.error("Action failed:", action, error);
      toast(error.message || "That action could not be completed.", {
        type: "error",
        title: "Something went wrong",
      });
    });
  });

  /* Overview ------------------------------------------------------------- */
  $("#briefing-refresh")?.addEventListener("click", (event) => {
    const button = event.currentTarget;
    handleAction("refresh-briefing", {}, button).catch(() => {});
  });

  /* Campus --------------------------------------------------------------- */
  $("#campus-refresh")?.addEventListener("click", async (event) => {
    const button = event.currentTarget;
    button.disabled = true;
    button.classList.add("spinning");
    try {
      await loadCampusView(true);
      toast("Campus feed refreshed from the official site and curated guide.", { title: "Up to date" });
    } catch (error) {
      toast(error.message, { type: "error", title: "Refresh failed" });
    } finally {
      button.disabled = false;
      button.classList.remove("spinning");
    }
  });
  $("#campus-search")?.addEventListener("input", (event) => {
    state.filters.campusQuery = event.target.value;
    renderCampus();
  });

  /* Opportunities -------------------------------------------------------- */
  $("#opp-refresh")?.addEventListener("click", async (event) => {
    const button = event.currentTarget;
    button.disabled = true;
    button.classList.add("spinning");
    try {
      await fetchOpportunities(true);
      renderOpportunities();
      toast("Opportunity radar refreshed.", { title: "Up to date" });
    } catch (error) {
      toast(error.message, { type: "error", title: "Refresh failed" });
    } finally {
      button.disabled = false;
      button.classList.remove("spinning");
    }
  });
  $("#opp-search")?.addEventListener("input", (event) => {
    state.filters.oppQuery = event.target.value;
    renderOpportunities();
  });
  $("#opp-mode")?.addEventListener("change", (event) => {
    state.filters.oppMode = event.target.value;
    renderOpportunities();
  });
  $("#opp-deadline")?.addEventListener("change", (event) => {
    state.filters.oppDeadline = event.target.value;
    renderOpportunities();
  });

  /* News ----------------------------------------------------------------- */
  $("#news-branch")?.addEventListener("change", async (event) => {
    const branch = event.target.value;
    state.profile.branch = branch;
    state.loaded.news = false;
    updateProfileUI();
    try {
      await api("/api/profile", { method: "PATCH", body: { branch } });
    } catch {
      /* keep the local preference even if the write fails */
    }
    try {
      await loadNewsView(true);
    } catch (error) {
      toast(error.message, { type: "error", title: "Could not load that branch" });
    }
  });
  $("#news-refresh")?.addEventListener("click", async (event) => {
    const button = event.currentTarget;
    button.disabled = true;
    button.classList.add("spinning");
    try {
      await loadNewsView(true);
      toast("Briefings refreshed.", { title: "Up to date" });
    } catch (error) {
      toast(error.message, { type: "error", title: "Refresh failed" });
    } finally {
      button.disabled = false;
      button.classList.remove("spinning");
    }
  });
  $("#news-search")?.addEventListener("input", (event) => {
    state.filters.newsQuery = event.target.value;
    renderNews();
  });

  /* Mail ----------------------------------------------------------------- */
 $("#gmail-refresh")?.addEventListener("click", async (event) => {
  const button = event.currentTarget;
  button.disabled = true;

  try {
    await loadGmailInbox();
    toast("Gmail inbox refreshed.", { title: "Up to date" });
  } catch (error) {
    toast(error.message, { type: "error", title: "Refresh failed" });
  } finally {
    button.disabled = false;
  }
});

$("#gmail-analyse")?.addEventListener("click", async (event) => {
  const button = event.currentTarget;
  button.disabled = true;
  button.textContent = "Analysing...";

  try {
    const result = await api("/api/gmail/analyse", {
      method: "POST",
    });

    await loadGmailPriority();

    toast(
      `Analysed ${result.processed} emails. ${result.failed} failed.`,
      { title: "Gmail analysis complete" }
    );
  } catch (error) {
    toast(error.message, {
      type: "error",
      title: "Analysis failed",
    });
  } finally {
    button.disabled = false;
    button.textContent = "Analyse Gmail";
  }
});

$("#gmail-load-more")?.addEventListener("click", async () => {
  await loadGmailInbox(true);
});

  /* Vault ---------------------------------------------------------------- */
  $("#vault-add")?.addEventListener("click", () => openVaultModal(null));
  $("#vault-search")?.addEventListener("input", (event) => {
    state.filters.vaultQuery = event.target.value;
    renderVault();
  });
  $("#vault-type")?.addEventListener("change", (event) => {
    state.filters.vaultType = event.target.value;
    renderVault();
  });
  $("#vault-scope")?.addEventListener("change", (event) => {
    state.filters.vaultScope = event.target.value;
    renderVault();
  });

  /* Tasks ---------------------------------------------------------------- */
  $("#task-add")?.addEventListener("click", () => openTaskModal(null, { priority: "medium", status: "todo" }));
  $("#task-search")?.addEventListener("input", (event) => {
    state.filters.taskQuery = event.target.value;
    renderTasks();
  });
  $("#task-priority")?.addEventListener("change", (event) => {
    state.filters.taskPriority = event.target.value;
    renderTasks();
  });

  /* Settings ------------------------------------------------------------- */
  $("#settings-form")?.addEventListener("submit", handleSettingsSubmit);

  /* Routing -------------------------------------------------------------- */
  window.addEventListener("hashchange", () => {
    route();
    document.body.classList.remove("nav-open");
  });

  // Close mobile navigation after choosing a link.
  $$("[data-nav]").forEach((link) => {
    link.addEventListener("click", () => {
      document.body.classList.remove("nav-open");
      $("#menu-btn")?.setAttribute("aria-expanded", "false");
    });
  });
}

/* --------------------------------------------------------------------------
   Start
   -------------------------------------------------------------------------- */

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", boot);
} else {
  boot();
}
