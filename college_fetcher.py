"""MIT-WPU campus updates discovery.

The fetcher scrapes a handful of likely notice pages on the configured college
website, classifies links, extracts deadlines and enriches each item with a
short "TL;DR" and "What to do" section. When the website is unreachable (or
renders entirely client-side), a curated campus guide is merged in so students
still get a useful, clearly-labelled feed.
"""

from __future__ import annotations

import logging
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from ai_summarizer import extract_deadlines
from config import Config

logger = logging.getLogger(__name__)

DEFAULT_LIMIT = 12
MAX_LIMIT = 30
REQUEST_TIMEOUT = min(Config.REQUEST_TIMEOUT, 9)

CANDIDATE_PATHS = [
    "",
    "/notices",
    "/news",
    "/events",
    "/announcements",
    "/examination",
    "/students",
]

KEYWORDS = {
    "Examination": [
        "exam",
        "examination",
        "timetable",
        "time-table",
        "hall ticket",
        "admit card",
        "result",
        "revaluation",
        "backlog",
        "viva",
    ],
    "Placement": [
        "placement",
        "internship",
        "recruit",
        "interview",
        "career",
        "training and placement",
    ],
    "Event": [
        "event",
        "fest",
        "workshop",
        "seminar",
        "conference",
        "competition",
        "hackathon",
        "webinar",
        "sports",
        "cultural",
    ],
    "Club": ["club", "committee", "chapter", "society", "community", "induction"],
    "Administration": [
        "scholarship",
        "fee",
        "hostel",
        "transport",
        "document",
        "verification",
        "certificate",
        "id card",
        "accounts",
        "admission",
    ],
    "Academic": [
        "academic calendar",
        "academic schedule",
        "lecture schedule",
        "class schedule",
        "syllabus",
        "holiday",
        "deadline",
        "registration",
        "assignment",
        "project",
        "semester",
    ],
    "Notice": [
        "notice",
        "announcement",
        "circular",
        "notification",
        "important information",
    ],
}

SKIP_TERMS = (
    "login",
    "sign in",
    "sign up",
    "apply now",
    "read more",
    "click here",
    "view all",
    "home",
    "about us",
    "contact us",
    "privacy policy",
    "terms of use",
    "facebook",
    "instagram",
    "linkedin",
    "youtube",
    "twitter",
    "x (twitter)",
    "sitemap",
    "careers",
    "gallery",
)

PRIORITY_TERMS = (
    "notice",
    "exam",
    "result",
    "admission",
    "scholarship",
    "event",
    "placement",
    "deadline",
    "important",
    "circular",
    "timetable",
    "registration",
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36 "
        "StudentEcosystem/2.0 (+campus notices)"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-IN,en;q=0.9",
}

SESSION = requests.Session()
SESSION.headers.update(HEADERS)


def _classify(text: str) -> str:
    lowered = text.lower()
    for category, keywords in KEYWORDS.items():
        if any(keyword in lowered for keyword in keywords):
            return category
    return "General"


def _is_same_site(url: str, base_url: str) -> bool:
    try:
        target = urlparse(url)
        base = urlparse(base_url)
        if target.scheme not in {"http", "https"} or not target.hostname:
            return False
        base_host = (base.hostname or "").lower()
        target_host = target.hostname.lower()
        base_root = ".".join(base_host.split(".")[-2:])
        target_root = ".".join(target_host.split(".")[-2:])
        return target_root == base_root
    except ValueError:
        return False


def _clean(text: str, limit: int = 500) -> str:
    text = re.sub(r"\s+", " ", text or "").strip()
    return text[:limit]


def _is_useful_title(title: str) -> bool:
    lowered = title.lower().strip()
    if len(lowered) < 12 or len(lowered) > 220:
        return False
    if lowered in SKIP_TERMS:
        return False
    if any(lowered == term or lowered.startswith(term + " ") for term in ("home", "about", "contact")):
        return False
    if lowered.count(" ") < 2:
        return False
    return True


def _score(update: dict) -> int:
    score = 0
    searchable = f"{update['title']} {update['link']}".lower()
    for term in PRIORITY_TERMS:
        if term in searchable:
            score += 2
    if update.get("deadline"):
        score += 3
    if update.get("category") != "General":
        score += 1
    if re.search(r"/20(2[4-9]|3[0-9])/", update["link"]):
        score += 2
    return score


def _tldr_for(update: dict) -> str:
    description = _clean(update.get("description", ""), 260)
    title = update.get("title", "")
    if description and description.lower() != title.lower():
        if title.lower() in description.lower():
            return description
        return f"{title}. {description}"
    category = update.get("category", "Campus")
    return f"{category} update from the MIT-WPU website: {title}."


def _what_to_do(update: dict) -> list[str]:
    actions: list[str] = []
    category = update.get("category")
    deadline = update.get("deadline")

    if deadline:
        try:
            days_left = (date.fromisoformat(deadline) - date.today()).days
        except ValueError:
            days_left = 0
        if days_left >= 0:
            actions.append(f"Add {deadline} to your task hub and plan backwards from it.")
        else:
            actions.append("That date has passed — check the official page for the next cycle.")
    if category == "Examination":
        actions.append("Verify the timetable and eligibility details with your department.")
        actions.append("Keep your hall ticket, ID and stationery ready in advance.")
    elif category == "Placement":
        actions.append("Update your resume and register through the placement cell.")
        actions.append("Prepare a 90-second introduction for the role.")
    elif category == "Event":
        actions.append("Check the venue, time and registration link on the official page.")
        actions.append("Block the slot in your calendar so it does not clash with classes.")
    elif category == "Administration":
        actions.append("Collect the required documents before visiting the desk.")
        actions.append("Keep a screenshot or receipt of every submission.")
    elif category == "Club":
        actions.append("Shortlist the club that best matches your branch and interests.")
        actions.append("Attend one session before the induction closes.")
    elif category == "Academic":
        actions.append("Confirm the exact requirement and deadline with your faculty.")
        actions.append("Break the work into tasks and start the first step today.")
    else:
        actions.append("Open the official link and confirm the details.")
        actions.append("Save it or convert it into a task if it affects you.")
    return actions[:3]


def _extract_links(html: str, page_url: str, base_url: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    for element in soup(["script", "style", "noscript", "svg", "nav", "footer"]):
        element.decompose()

    updates: list[dict] = []
    seen: set[str] = set()

    for anchor in soup.find_all("a", href=True):
        title = _clean(anchor.get_text(" ", strip=True), 240)
        href = (anchor.get("href") or "").strip()
        if not title or not href or not _is_useful_title(title):
            continue
        if href.startswith(("#", "mailto:", "tel:", "javascript:")):
            continue

        absolute = urljoin(page_url, href)
        if not _is_same_site(absolute, base_url) or absolute in seen:
            continue
        if any(absolute.lower().endswith(ext) for ext in (".jpg", ".png", ".pdf")) and len(title) < 24:
            continue

        searchable = f"{title} {absolute}"
        category = _classify(searchable)

        parent = anchor.find_parent(["li", "article", "tr", "div", "section"])
        description = ""
        if parent:
            description = _clean(parent.get_text(" ", strip=True), 420)
        if not description or len(description) < len(title):
            description = title

        deadline = None
        if len(description) > 25:
            found = extract_deadlines(f"{title}. {description}", limit=1)
            if found:
                deadline = found[0].get("date")

        seen.add(absolute)
        updates.append(
            {
                "title": title,
                "link": absolute,
                "source": urlparse(base_url).hostname or "mitwpu.edu.in",
                "description": description,
                "category": category,
                "deadline": deadline,
                "published_at": None,
            }
        )
    return updates


def _fetch_page(url: str) -> tuple[str, str]:
    try:
        response = SESSION.get(url, timeout=REQUEST_TIMEOUT, allow_redirects=True)
        response.raise_for_status()
        content_type = response.headers.get("Content-Type", "").lower()
        if "html" not in content_type and "<html" not in response.text.lower()[:500]:
            return url, ""
        if not _is_same_site(response.url, url):
            return url, ""
        return response.url, response.text
    except requests.RequestException:
        return url, ""
    except Exception:
        logger.exception("Unexpected error fetching %s", url)
        return url, ""


def get_college_updates(base_url: str | None = None, limit: int = DEFAULT_LIMIT) -> list[dict]:
    """Return MIT-WPU updates, merging curated content when live data is thin."""
    base_url = (base_url or Config.COLLEGE_WEBSITE_URL or "").strip()
    if not base_url:
        base_url = "https://mitwpu.edu.in/"

    try:
        limit = max(1, min(int(limit), MAX_LIMIT))
    except (TypeError, ValueError):
        limit = DEFAULT_LIMIT

    parsed = urlparse(base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        logger.warning("Invalid college website URL configured.")
        live: list[dict] = []
    else:
        urls = []
        for path in CANDIDATE_PATHS:
            candidate = urljoin(base_url if base_url.endswith("/") else base_url + "/", path.lstrip("/"))
            if candidate not in urls:
                urls.append(candidate)

        live = []
        seen: set[str] = set()
        with ThreadPoolExecutor(max_workers=3) as pool:
            futures = {pool.submit(_fetch_page, url): url for url in urls[:4]}
            for future in as_completed(futures):
                final_url, html = future.result()
                if not html:
                    continue
                for item in _extract_links(html, final_url, base_url):
                    if item["link"] in seen:
                        continue
                    # Ignore the homepage and generic landing links.
                    if urlparse(item["link"]).path in {"", "/"}:
                        continue
                    seen.add(item["link"])
                    live.append(item)

        for item in live:
            item["tldr"] = _tldr_for(item)
            item["what_to_do"] = _what_to_do(item)
            item["urgency"] = (
                "high" if item.get("deadline") else "medium"
            )
            item["tags"] = [item["category"].lower(), "mit-wpu"]
            item["curated"] = False
            item["whats_new"] = True
            item["_score"] = _score(item)

        live.sort(key=lambda entry: entry.get("_score", 0), reverse=True)
        for item in live:
            item.pop("_score", None)

    live = live[: max(1, limit // 2)] if live else []

    if len(live) < limit:
        from seed_data import get_campus_guide

        guide = get_campus_guide()
        existing_titles = {item["title"].lower() for item in live}
        existing_links = {item["link"] for item in live}
        for item in guide:
            if item["title"].lower() in existing_titles or item["link"] in existing_links:
                continue
            live.append(item)
            if len(live) >= limit:
                break

    return live[:limit]


def live_status(updates: list[dict]) -> dict:
    live = sum(1 for item in updates if not item.get("curated"))
    return {
        "live_count": live,
        "curated_count": len(updates) - live,
        "source": Config.COLLEGE_WEBSITE_URL,
        "mode": "live" if live else "curated",
    }
