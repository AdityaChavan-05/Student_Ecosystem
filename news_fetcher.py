import logging
import time
from datetime import datetime, timezone
from urllib.parse import quote

import feedparser
import requests

from categories import BRANCH_MAPPINGS, GENERAL_CATEGORIES


logger = logging.getLogger(__name__)

REQUEST_TIMEOUT = 15
DEFAULT_LIMIT = 10

RSS_URL = (
    "https://news.google.com/rss/search"
    "?q={query}&hl=en-IN&gl=IN&ceid=IN:en"
)

_session = requests.Session()
_session.headers.update(
    {
        "User-Agent": (
            "Mozilla/5.0 (compatible; StudentEcosystem/1.0)"
        )
    }
)


def _parse_published_date(date_string):
    """Convert an RSS publication date into a UTC ISO timestamp."""
    if not date_string:
        return None

    try:
        parsed = feedparser._parse_date(date_string)

        if not parsed:
            return None

        published = datetime(*parsed[:6], tzinfo=timezone.utc)
        return published.isoformat()

    except (TypeError, ValueError, OverflowError):
        return None


def _fetch_rss_articles(query, limit=DEFAULT_LIMIT):
    """Fetch articles matching a search query from Google News RSS."""
    encoded_query = quote(query)
    url = RSS_URL.format(query=encoded_query)

    try:
        response = _session.get(
            url,
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()

        feed = feedparser.parse(response.content)

        articles = []

        for entry in feed.entries[:limit]:
            title = entry.get("title", "").strip()
            link = entry.get("link", "").strip()

            if not title or not link:
                continue

            source_info = entry.get("source", {})
            source_name = source_info.get("title", "")

            articles.append(
                {
                    "title": title,
                    "link": link,
                    "url": link,
                    "source": source_name or "Google News",
                    "description": entry.get(
                        "summary", ""
                    ),
                    "published_at": _parse_published_date(
                        entry.get("published", "")
                    ),
                    "category": query,
                }
            )

        return articles

    except (requests.RequestException, ValueError):
        logger.warning(
            "Could not retrieve news for the requested query."
        )
        return []


def get_news(branch="Computer Science", limit=DEFAULT_LIMIT):
    """
    Retrieve engineering news relevant to the selected branch.

    Returns a list of article dictionaries.
    """
    if not isinstance(branch, str):
        branch = "Computer Science"

    branch = branch.strip()

    if branch not in BRANCH_MAPPINGS:
        branch = "Computer Science"

    try:
        limit = max(1, min(int(limit), 30))
    except (TypeError, ValueError):
        limit = DEFAULT_LIMIT

    branch_topics = BRANCH_MAPPINGS.get(branch, [])
    queries = branch_topics + GENERAL_CATEGORIES

    articles = []
    seen_links = set()

    # Search branch-specific topics first.
    for query in queries:
        remaining = limit - len(articles)

        if remaining <= 0:
            break

        results = _fetch_rss_articles(
            query,
            limit=min(remaining, 10),
        )

        for article in results:
            link = article.get("link", "")

            if not link or link in seen_links:
                continue

            seen_links.add(link)
            article["branch"] = branch
            articles.append(article)

            if len(articles) >= limit:
                break

        # Avoid sending too many requests in quick succession.
        time.sleep(0.2)

    return articles
