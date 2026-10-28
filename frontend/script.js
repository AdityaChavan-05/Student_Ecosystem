```javascript
"use strict";

/* =========================================
   STUDENT ECOSYSTEM — FRONTEND CONTROLLER
   ========================================= */

const API = {
    news: "/api/news",
    college: "/api/college-updates"
};

document.addEventListener("DOMContentLoaded", () => {
    updateCurrentYear();
    initializeNews();
    initializeCollegeUpdates();
});

/* =========================================
   GENERAL HELPERS
   ========================================= */

function updateCurrentYear() {
    const yearElement = document.getElementById("current-year");

    if (yearElement) {
        yearElement.textContent = new Date().getFullYear();
    }
}

function createElement(tag, className, text) {
    const element = document.createElement(tag);

    if (className) {
        element.className = className;
    }

    if (text !== undefined && text !== null) {
        element.textContent = String(text);
    }

    return element;
}

function setStatus(element, message, isError = false) {
    if (!element) return;

    element.textContent = message;
    element.classList.toggle("status-error", isError);
}

function showLoading(container, message) {
    if (!container) return;

    container.replaceChildren();

    const loading = createElement("div", "loading-indicator");
    const spinner = createElement("span", "loading-spinner");

    spinner.setAttribute("aria-hidden", "true");

    loading.append(
        spinner,
        createElement("span", "", message)
    );

    container.appendChild(loading);
}

function showEmptyState(container, title, message) {
    if (!container) return;

    const card = createElement("article", "news-placeholder");
    const icon = createElement("div", "placeholder-icon", "✦");

    icon.setAttribute("aria-hidden", "true");

    card.append(
        icon,
        createElement("h3", "", title),
        createElement("p", "", message)
    );

    container.replaceChildren(card);
}

async function fetchJSON(url) {
    const response = await fetch(url, {
        headers: {
            Accept: "application/json"
        }
    });

    let data;

    try {
        data = await response.json();
    } catch {
        throw new Error("The server returned an invalid response.");
    }

    if (!response.ok) {
        throw new Error(
            data.error || `Request failed with status ${response.status}.`
        );
    }

    return data;
}

function formatDate(value) {
    if (!value) return "Date unavailable";

    const date = new Date(value);

    if (Number.isNaN(date.getTime())) {
        return "Date unavailable";
    }

    return new Intl.DateTimeFormat("en-IN", {
        day: "numeric",
        month: "short",
        year: "numeric"
    }).format(date);
}

function createSafeExternalLink(url, label, className = "") {
    const link = createElement("a", className, label);

    try {
        const parsedURL = new URL(url);

        if (!["http:", "https:"].includes(parsedURL.protocol)) {
            return null;
        }

        link.href = parsedURL.href;
        link.target = "_blank";
        link.rel = "noopener noreferrer";

        return link;
    } catch {
        return null;
    }
}

/* =========================================
   ENGINEERING NEWS
   ========================================= */

function initializeNews() {
    const branchSelect = document.getElementById("branch-select");
    const refreshButton = document.getElementById("refresh-news");
    const newsContainer = document.getElementById("news-container");
    const newsStatus = document.getElementById("news-status");

    if (!branchSelect || !refreshButton || !newsContainer) {
        return;
    }

    const savedBranch = localStorage.getItem("student-ecosystem-branch");

    if (
        savedBranch &&
        Array.from(branchSelect.options).some(
            option => option.value === savedBranch
        )
    ) {
        branchSelect.value = savedBranch;
    }

    async function loadNews(forceRefresh = false) {
        const branch = branchSelect.value;

        localStorage.setItem("student-ecosystem-branch", branch);

        const params = new URLSearchParams({
            branch,
            limit: "8"
        });

        if (forceRefresh) {
            params.set("refresh", "true");
        }

        refreshButton.disabled = true;
        refreshButton.textContent = forceRefresh
            ? "Refreshing…"
            : "Loading news…";

        setStatus(newsStatus, "Finding engineering news for your branch…");
        showLoading(newsContainer, "Loading articles and preparing AI summaries…");

        try {
            const data = await fetchJSON(`${API.news}?${params.toString()}`);

            renderNews(newsContainer, data.articles || []);

            const count = Number(data.count ?? (data.articles || []).length);
            const countElement = document.getElementById("news-count");

            if (countElement) {
                countElement.textContent =
                    `${count} ${count === 1 ? "article" : "articles"}`;
            }

            if (count > 0) {
                setStatus(
                    newsStatus,
                    `Showing ${count} article${count === 1 ? "" : "s"} for ${branch}.`
                );
            } else {
                setStatus(
                    newsStatus,
                    "No articles were found right now. Try refreshing in a little while."
                );
            }
        } catch (error) {
            console.error("Unable to load engineering news:", error);

            showEmptyState(
                newsContainer,
                "We couldn't load the news",
                "Please check your connection and try again. If the problem continues, the backend or news source may be unavailable."
            );

            setStatus(
                newsStatus,
                error.message || "Something went wrong while loading news.",
                true
            );
        } finally {
            refreshButton.disabled = false;

            const isDashboard = window.location.pathname === "/";

            refreshButton.replaceChildren(
                createElement(
                    "span",
                    "",
                    "↻"
                ),
                document.createTextNode(
                    isDashboard ? " Refresh news" : " Get latest news"
                )
            );
        }
    }

    refreshButton.addEventListener("click", () => {
        loadNews(true);
    });

    branchSelect.addEventListener("change", () => {
        loadNews(false);
    });

    loadNews(false);
}

function renderNews(container, articles) {
    if (!container) return;

    if (!Array.isArray(articles) || articles.length === 0) {
        showEmptyState(
            container,
            "No news articles available",
            "There are no matching articles at the moment. Please try again later."
        );
        return;
    }

    const fragment = document.createDocumentFragment();

    articles.forEach(article => {
        fragment.appendChild(createNewsCard(article));
    });

    container.replaceChildren(fragment);
}

function createNewsCard(article) {
    const card = createElement("article", "news-card");

    const metadata = createElement("div", "news-card-meta");
    metadata.appendChild(
        createElement("span", "news-source", article.source || "Engineering News")
    );

    const published = formatDate(article.published_at);

    metadata.appendChild(
        createElement("span", "article-date", published)
    );

    const title = createElement("h3");
    const titleLink = createSafeExternalLink(
        article.link,
        article.title || "Untitled article"
    );

    if (titleLink) {
        title.appendChild(titleLink);
    } else {
        title.textContent = article.title || "Untitled article";
    }

    card.append(metadata, title);

    if (article.description) {
        card.appendChild(
            createElement(
                "p",
                "news-description",
                article.description
            )
        );
    }

    if (article.summary) {
        const summaryBox = createElement("div", "summary-box");

        summaryBox.appendChild(
            createElement("div", "summary-label", "✧ AI Summary")
        );

        const summaryList = createElement("ul");

        const bullets = String(article.summary)
            .split(/\r?\n/)
            .map(line => line.replace(/^\s*(?:[-*•]+|\d+[.)])\s*/, "").trim())
            .filter(Boolean);

        if (bullets.length > 0) {
            bullets.forEach(bullet => {
                summaryList.appendChild(
                    createElement("li", "", bullet)
                );
            });
        } else {
            summaryList.appendChild(
                createElement("li", "", article.summary)
            );
        }

        summaryBox.appendChild(summaryList);
        card.appendChild(summaryBox);
    }

    const footer = createElement("div", "news-card-footer");

    footer.appendChild(
        createElement("span", "article-date", published)
    );

    const readLink = createSafeExternalLink(
        article.link,
        "Read original article →",
        "article-link"
    );

    if (readLink) {
        footer.appendChild(readLink);
    }

    card.appendChild(footer);

    return card;
}

/* =========================================
   COLLEGE UPDATES
   ========================================= */

function initializeCollegeUpdates() {
    const collegeContainer = document.getElementById("college-container");
    const collegeStatus = document.getElementById("college-status");
    const refreshButton = document.getElementById("refresh-college");
    const categorySelect = document.getElementById("college-category");

    if (!collegeContainer) {
        return;
    }

    let allUpdates = [];

    async function loadCollegeUpdates(forceRefresh = false) {
        if (refreshButton) {
            refreshButton.disabled = true;
            refreshButton.textContent = forceRefresh
                ? "Refreshing…"
                : "Loading updates…";
        }

        setStatus(collegeStatus, "Checking for college notices and announcements…");
        showLoading(collegeContainer, "Loading college updates…");

        const params = new URLSearchParams({
            limit: "30"
        });

        if (forceRefresh) {
            params.set("refresh", "true");
        }

        try {
            const data = await fetchJSON(
                `${API.college}?${params.toString()}`
            );

            allUpdates = Array.isArray(data.updates) ? data.updates : [];

            if (data.college_website_configured === false) {
                showEmptyState(
                    collegeContainer,
                    "Your college portal hasn't been connected yet",
                    "This is expected for now. Once the official college website URL is added to the project settings, available notices and announcements can appear here."
                );

                setStatus(
                    collegeStatus,
                    "College website not configured yet. We'll connect it once you have the official URL."
                );

                return;
            }

            renderCollegeUpdates(
                collegeContainer,
                allUpdates,
                categorySelect ? categorySelect.value : "all"
            );

            setStatus(
                collegeStatus,
                allUpdates.length
                    ? `Found ${allUpdates.length} college update${allUpdates.length === 1 ? "" : "s"}.`
                    : "No college updates were found. Try refreshing later."
            );
        } catch (error) {
            console.error("Unable to load college updates:", error);

            showEmptyState(
                collegeContainer,
                "College updates aren't available",
                "Please try again later. Check that the backend is running and the college website is configured."
            );

            setStatus(
                collegeStatus,
                error.message || "Something went wrong while loading college updates.",
                true
            );
        } finally {
            if (refreshButton) {
                refreshButton.disabled = false;

                refreshButton.replaceChildren(
                    createElement("span", "", "↻"),
                    document.createTextNode(" Refresh updates")
                );
            }
        }
    }

    if (refreshButton) {
        refreshButton.addEventListener("click", () => {
            loadCollegeUpdates(true);
        });
    }

    if (categorySelect) {
        categorySelect.addEventListener("change", () => {
            renderCollegeUpdates(
                collegeContainer,
                allUpdates,
                categorySelect.value
            );
        });
    }

    loadCollegeUpdates(false);
}

function renderCollegeUpdates(container, updates, selectedCategory = "all") {
    if (!container) return;

    const filteredUpdates = selectedCategory === "all"
        ? updates
        : updates.filter(
            update => update.category === selectedCategory
        );

    if (filteredUpdates.length === 0) {
        showEmptyState(
            container,
            "No updates in this category",
            "Try another category or check again later for new announcements."
        );
        return;
    }

    const fragment = document.createDocumentFragment();

    filteredUpdates.forEach(update => {
        fragment.appendChild(createCollegeUpdateCard(update));
    });

    container.replaceChildren(fragment);
}

function createCollegeUpdateCard(update) {
    const card = createElement("article", "college-update-card");

    const icon = createElement(
        "div",
        "update-icon",
        getCollegeCategoryIcon(update.category)
    );

    icon.setAttribute("aria-hidden", "true");

    const content = createElement("div", "update-content");

    content.appendChild(
        createElement(
            "h3",
            "",
            update.title || "College update"
        )
    );

    if (update.description) {
        content.appendChild(
            createElement("p", "", update.description)
        );
    }

    const metadata = createElement("div", "update-meta");

    metadata.appendChild(
        createElement(
            "span",
            "update-category",
            update.category || "Notice"
        )
    );

    if (update.published_at) {
        metadata.appendChild(
            createElement(
                "span",
                "",
                formatDate(update.published_at)
            )
        );
    }

    content.appendChild(metadata);

    const sourceLink = createSafeExternalLink(
        update.link,
        "View official update →",
        "update-link"
    );

    if (sourceLink) {
        content.appendChild(sourceLink);
    }

    card.append(icon, content);

    return card;
}

function getCollegeCategoryIcon(category) {
    const icons = {
        Examination: "◷",
        Notice: "▤",
        Event: "✧",
        Academic: "▥"
    };

    return icons[category] || "▤";
}
```
