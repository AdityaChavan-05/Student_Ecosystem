"""Engineering news aggregation.

Sources are tried in order and merged:

1. Google News RSS for the branch's topic query.
2. Bing News RSS as a secondary source.
3. Curated engineering publication feeds.
4. A bundled reading list so the feature never renders empty.

Any failure is logged and skipped; the function always returns a list.
"""

from __future__ import annotations

import logging
import random
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html import unescape
from urllib.parse import quote

import feedparser
import requests
from bs4 import BeautifulSoup

from categories import BRANCH_MAPPINGS, GENERAL_CATEGORIES
from config import Config

logger = logging.getLogger(__name__)

DEFAULT_LIMIT = Config.DEFAULT_NEWS_LIMIT
MAX_LIMIT = Config.MAX_NEWS_LIMIT

GOOGLE_NEWS_URL = (
    "https://news.google.com/rss/search?q={query}&hl=en-IN&gl=IN&ceid=IN:en"
)
BING_NEWS_URL = "https://www.bing.com/news/search?q={query}&format=rss&setlang=en-in"

PUBLICATION_FEEDS = [
    ("IEEE Spectrum", "https://spectrum.ieee.org/feeds/feed.rss"),
    ("MIT News", "https://news.mit.edu/rss/topic/engineering"),
    ("Ars Technica", "https://feeds.arstechnica.com/arstechnica/index"),
    ("The Verge", "https://www.theverge.com/rss/index.xml"),
]

SESSION = requests.Session()
SESSION.headers.update(
    {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0 Safari/537.36 StudentEcosystem/2.0"
        ),
        "Accept": "application/rss+xml, application/xml, text/xml, */*",
    }
)

BRANCH_FILTERS = {
    "Computer Science": (
        "software",
        "programming",
        "developer",
        "computer",
        "cloud",
        "security",
        "cyber",
        "algorithm",
        "code",
        "open source",
        "database",
        "web",
        "linux",
    ),
    "Artificial Intelligence": (
        "ai",
        "artificial intelligence",
        "machine learning",
        "model",
        "neural",
        "robot",
        "llm",
        "deep learning",
        "data",
        "gpu",
        "openai",
        "gemini",
    ),
    "Electronics": (
        "chip",
        "semiconductor",
        "electronics",
        "embedded",
        "iot",
        "sensor",
        "circuit",
        "battery",
        "hardware",
        "quantum",
        "silicon",
    ),
    "Mechanical": (
        "mechanical",
        "manufactur",
        "robot",
        "automotive",
        "3d print",
        "material",
        "engine",
        "turbine",
        "aerospace",
        "energy",
    ),
    "Civil": (
        "civil",
        "construction",
        "structural",
        "concrete",
        "infrastructure",
        "urban",
        "bridge",
        "smart city",
        "building",
    ),
    "Electrical": (
        "electric",
        "power",
        "grid",
        "battery",
        "energy",
        "voltage",
        "semiconductor",
        "motor",
        "solar",
        "renewable",
    ),
    "Science and Technology": (
        "science",
        "research",
        "physics",
        "chemistry",
        "space",
        "quantum",
        "laboratory",
        "discovery",
        "innovation",
        "technology",
    ),
}


def clean_text(text: str) -> str:
    """Remove HTML tags and collapse whitespace."""
    if not text:
        return ""
    try:
        soup = BeautifulSoup(unescape(str(text)), "html.parser")
        return " ".join(soup.get_text(" ", strip=True).split())
    except Exception:
        return re.sub(r"\s+", " ", str(text)).strip()


def strip_source_suffix(title: str, source: str) -> str:
    """Remove a trailing ' - Publisher' suffix that RSS feeds append to headlines."""
    title = (title or "").strip()
    source = (source or "").strip()
    if not title or not source or len(source) < 3:
        return title
    lowered = title.lower()
    for separator in (" - ", " | ", " – ", " — ", " :: "):
        suffix = f"{separator}{source.lower()}"
        if lowered.endswith(suffix):
            trimmed = title[: -len(suffix)].strip()
            if len(trimmed) >= 12:
                return trimmed
    return title


def parse_date(date_string: str) -> str | None:
    """Convert RSS publication dates into UTC ISO strings."""
    if not date_string:
        return None
    try:
        published = parsedate_to_datetime(date_string)
        if published.tzinfo is None:
            published = published.replace(tzinfo=timezone.utc)
        return published.astimezone(timezone.utc).isoformat(timespec="seconds")
    except (TypeError, ValueError, OverflowError, IndexError):
        return None


def _jittered_delay(seconds: float) -> float:
    """Add small jitter so concurrent workers do not retry in lockstep."""
    return max(0.0, seconds) * random.uniform(0.75, 1.25)


def _retry_delay(response=None, attempt: int = 1) -> float | None:
    """Return a bounded backoff, or None when we should respect the limit."""
    if attempt >= max(1, Config.NEWS_FETCH_ATTEMPTS):
        return None

    retry_after = None
    headers = getattr(response, "headers", None)
    if headers:
        try:
            retry_after = float(headers.get("Retry-After", ""))
        except (TypeError, ValueError):
            retry_after = None
    if retry_after is not None:
        # A long Retry-After means the provider wants us to stop, not sleep.
        if retry_after > Config.NEWS_RETRY_MAX_SECONDS:
            return None
        return _jittered_delay(retry_after)

    backoff = Config.NEWS_RETRY_BASE_SECONDS * (2 ** (attempt - 1))
    return _jittered_delay(min(backoff, Config.NEWS_RETRY_MAX_SECONDS))


def _entries_to_articles(feed, source_hint: str = "") -> list[dict]:
    """Convert a parsed feed into the article shape used by the app."""
    articles = []
    for entry in getattr(feed, "entries", []) or []:
        title = clean_text(entry.get("title", ""))
        link = (entry.get("link") or "").strip()
        if not title or not link:
            continue

        source_info = entry.get("source", {}) or {}
        source = clean_text(source_info.get("title", "")) if isinstance(source_info, dict) else ""
        title = strip_source_suffix(title, source or source_hint)
        description = clean_text(
            entry.get("summary")
            or entry.get("description")
            or (entry.get("content") or [{}])[0].get("value", "")
        )
        # Feeds sometimes bundle several stories into one entry ("Read more here"
        # then a new headline); keep only the first story's text.
        description = re.split(r"\s+Read more\b", description, maxsplit=1)[0].strip()
        if len(description) < 40:
            description = clean_text(entry.get("title", ""))

        articles.append(
            {
                "title": title,
                "link": link,
                "url": link,
                "source": source or source_hint or "Engineering publisher",
                "description": description[:4000],
                "content": description[:4000],
                "published_at": parse_date(
                    entry.get("published", "") or entry.get("updated", "")
                ),
            }
        )
    return articles


def _fetch_rss_status(url: str, source_hint: str = "") -> tuple[list[dict], str]:
    """Download one RSS feed with a single bounded retry on transient errors.

    Returns ``(articles, status)`` where status is ``ok``, ``empty``,
    ``throttled`` or ``error``. Callers can use ``throttled`` to prefer a cached
    feed instead of replacing it with a curated fallback.
    """
    throttled = False
    for attempt in range(1, max(1, Config.NEWS_FETCH_ATTEMPTS) + 1):
        try:
            response = SESSION.get(url, timeout=Config.REQUEST_TIMEOUT)
            if getattr(response, "status_code", 200) == 429:
                throttled = True
                delay = _retry_delay(response, attempt)
                if delay is not None:
                    logger.info("%s is throttled; retrying once with backoff.", source_hint or url)
                    time.sleep(delay)
                    continue
                logger.info("%s is throttled; using cached or alternate sources.", source_hint or url)
                return [], "throttled"
            response.raise_for_status()
            articles = _entries_to_articles(feedparser.parse(response.content), source_hint)
            return articles, "ok" if articles else "empty"
        except requests.HTTPError as error:
            error_response = getattr(error, "response", None)
            status_code = getattr(error_response, "status_code", None)
            if status_code == 429:
                throttled = True
                delay = _retry_delay(error_response, attempt)
                if delay is not None:
                    time.sleep(delay)
                    continue
                return [], "throttled"
            if status_code is not None and 500 <= status_code < 600:
                delay = _retry_delay(error_response, attempt)
                if delay is not None:
                    time.sleep(delay)
                    continue
            logger.info("RSS request failed (%s): %s", source_hint or url, error)
            return [], "error"
        except requests.RequestException as error:
            delay = _retry_delay(None, attempt)
            if delay is not None:
                time.sleep(delay)
                continue
            logger.info("RSS request failed (%s): %s", source_hint or url, error)
            return [], "error"
        except Exception:
            logger.exception("Unexpected RSS parsing error for %s", source_hint or url)
            return [], "error"
    return [], "throttled" if throttled else "error"


def fetch_rss(url: str, source_hint: str = "") -> list[dict]:
    """Download and parse one RSS feed. Returns [] on any failure."""
    return _fetch_rss_status(url, source_hint)[0]


def _build_query(topics: list[str]) -> str:
    terms = [f'"{topic}"' for topic in topics if isinstance(topic, str) and topic.strip()]
    return " OR ".join(terms)


def _dedupe(articles: list[dict]) -> list[dict]:
    seen_links: set[str] = set()
    seen_titles: set[str] = set()
    unique = []
    for article in articles:
        link = (article.get("link") or "").strip()
        title_key = re.sub(r"\W+", "", (article.get("title") or "").lower())[:80]
        if not link or link in seen_links or title_key in seen_titles:
            continue
        seen_links.add(link)
        seen_titles.add(title_key)
        unique.append(article)
    return unique


def _matches_branch(article: dict, branch: str) -> bool:
    keywords = BRANCH_FILTERS.get(branch)
    if not keywords:
        return True
    text = f"{article.get('title', '')} {article.get('description', '')}".lower()
    return any(keyword in text for keyword in keywords)


def _substance(article: dict) -> int:
    """How much real text the feed carried beyond the headline."""
    title = re.sub(r"\W+", "", (article.get("title") or "").lower())
    description = re.sub(r"\W+", "", (article.get("description") or "").lower())
    return max(0, len(description) - len(title))


def _recency(article: dict) -> float:
    published = article.get("published_at")
    if not published:
        return 0.5
    try:
        moment = datetime.fromisoformat(published)
    except (TypeError, ValueError):
        return 0.5
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    age_days = (datetime.now(timezone.utc) - moment).total_seconds() / 86400
    return max(0.0, 5.0 - age_days / 4.0)


def _rank(article: dict, branch: str) -> float:
    """Prefer recent stories that actually include a summary, not bare headlines."""
    score = _recency(article)
    detail = _substance(article)
    if detail > 100:
        score += 2.5
    elif detail > 30:
        score += 1.0
    if _matches_branch(article, branch):
        score += 0.5
    return score


def fetch_publication_feeds(per_feed: int = 12) -> list[dict]:
    """Fetch curated publication feeds in parallel (best-effort, never raises)."""
    if not PUBLICATION_FEEDS:
        return []
    collected: list[dict] = []
    workers = max(1, min(len(PUBLICATION_FEEDS), 4))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(fetch_rss, url, name): name for name, url in PUBLICATION_FEEDS
        }
        for future in as_completed(futures):
            try:
                collected.extend(future.result()[:per_feed])
            except Exception:
                logger.info("Publication feed unavailable: %s", futures[future])
    return collected


def fetch_news(branch: str = "Computer Science", limit: int = DEFAULT_LIMIT) -> dict:
    """Fetch engineering news and report source health alongside the articles.

    ``throttled`` tells the app layer that Google/Bing asked it to slow down,
    so a recently cached feed can be reused instead of a curated fallback.
    """
    try:
        limit = max(1, min(int(limit), MAX_LIMIT))
    except (TypeError, ValueError):
        limit = DEFAULT_LIMIT

    if isinstance(branch, list):
        branch_name = "Engineering"
        topics = [topic for topic in branch if isinstance(topic, str)]
    else:
        branch_name = branch if branch in BRANCH_MAPPINGS else "Computer Science"
        topics = list(BRANCH_MAPPINGS.get(branch_name, []))

    topics = list(dict.fromkeys([*topics, *GENERAL_CATEGORIES]))
    query = _build_query(topics)
    if not query:
        return {
            "articles": _with_fallback([], branch_name, limit),
            "throttled": False,
            "source_status": {},
            "branch": branch_name,
        }

    encoded = quote(query, safe="")
    collected: list[dict] = []

    # Tier 1: Google News (broad, fresh, but often headline-only).
    google_articles, google_status = _fetch_rss_status(
        GOOGLE_NEWS_URL.format(query=encoded), "Google News"
    )
    collected.extend(google_articles)

    # Tier 2: Bing News.
    bing_articles, bing_status = _fetch_rss_status(
        BING_NEWS_URL.format(query=encoded), "Bing News"
    )
    collected.extend(bing_articles)

    # Tier 3: curated publication feeds — these carry real summaries, so always
    # pull them; ranking below decides what reaches the top of the feed.
    collected.extend(fetch_publication_feeds(per_feed=max(6, limit * 2)))

    collected = _dedupe(collected)

    # Keep branch-relevant stories, but never render an empty feed in a niche branch.
    relevant = [item for item in collected if _matches_branch(item, branch_name)]
    relevant_ids = {id(item) for item in relevant}
    others = [item for item in collected if id(item) not in relevant_ids]
    pool = relevant + others

    # Rank by recency + real summary text; slice after ranking.
    pool.sort(key=lambda item: _rank(item, branch_name), reverse=True)

    for article in pool:
        article["branch"] = branch_name
        article["fallback"] = False

    return {
        "articles": _with_fallback(pool[: max(limit, 3)], branch_name, limit),
        "throttled": "throttled" in (google_status, bing_status),
        "source_status": {"google": google_status, "bing": bing_status},
        "branch": branch_name,
    }


def get_news(branch: str = "Computer Science", limit: int = DEFAULT_LIMIT) -> list[dict]:
    """Backward-compatible wrapper returning only the article list."""
    return fetch_news(branch, limit=limit)["articles"]


def _with_fallback(articles: list[dict], branch: str, limit: int) -> list[dict]:
    if len(articles) >= 3:
        return articles[:limit]
    from seed_data import get_news_fallback

    fallback = get_news_fallback(limit)
    for item in fallback:
        item["branch"] = branch
    merged = _dedupe([*articles, *fallback])
    return merged[:limit]
