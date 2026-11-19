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
import re
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

DEFAULT_LIMIT = 9
MAX_LIMIT = 24

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


def fetch_rss(url: str, source_hint: str = "") -> list[dict]:
    """Download and parse one RSS feed. Returns [] on any failure."""
    try:
        response = SESSION.get(url, timeout=Config.REQUEST_TIMEOUT)
        response.raise_for_status()
        feed = feedparser.parse(response.content)
    except requests.RequestException as error:
        logger.info("RSS request failed (%s): %s", source_hint or url, error)
        return []
    except Exception:
        logger.exception("Unexpected RSS parsing error for %s", source_hint or url)
        return []

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


def get_news(branch: str = "Computer Science", limit: int = DEFAULT_LIMIT) -> list[dict]:
    """Fetch engineering news for a branch (or topic list).

    Returns a list of dicts with ``fallback`` set to False. If every source
    fails, a clearly-marked curated reading list is returned instead.
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
        return _with_fallback([], branch_name, limit)

    encoded = quote(query, safe="")
    collected: list[dict] = []

    # Tier 1: Google News (broad, fresh, but often headline-only).
    collected.extend(fetch_rss(GOOGLE_NEWS_URL.format(query=encoded), "Google News"))

    # Tier 2: Bing News.
    collected.extend(fetch_rss(BING_NEWS_URL.format(query=encoded), "Bing News"))

    # Tier 3: curated publication feeds — these carry real summaries, so always
    # pull them; ranking below decides what reaches the top of the feed.
    collected.extend(fetch_publication_feeds(per_feed=max(6, limit * 2)))

    collected = _dedupe(collected)

    # Keep branch-relevant stories, but never render an empty feed in a niche branch.
    relevant = [item for item in collected if _matches_branch(item, branch_name)]
    others = [item for item in collected if item not in relevant]
    pool = relevant + others

    # Rank by recency + real summary text; slice after ranking.
    pool.sort(key=lambda item: _rank(item, branch_name), reverse=True)

    for article in pool:
        article["branch"] = branch_name
        article["fallback"] = False

    return _with_fallback(pool[: max(limit, 3)], branch_name, limit)


def _with_fallback(articles: list[dict], branch: str, limit: int) -> list[dict]:
    if len(articles) >= 3:
        return articles[:limit]
    from seed_data import get_news_fallback

    fallback = get_news_fallback(limit)
    for item in fallback:
        item["branch"] = branch
    merged = _dedupe([*articles, *fallback])
    return merged[:limit]
