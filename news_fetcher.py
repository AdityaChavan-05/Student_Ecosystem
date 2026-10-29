import logging
import time

import feedparser
import requests

from urllib.parse import urlparse

logger = logging.getLogger(__name__)

GOOGLE_NEWS_RSS_URL = "https://news.google.com/rss/search"

REQUEST_TIMEOUT = 12
DEFAULT_LIMIT = 8
MAX_LIMIT = 10

def _format_publication_date(entry):
"""Convert an RSS publication date into a UTC ISO timestamp."""

published = entry.get("published_parsed")

if not published:
    published = entry.get("updated_parsed")

if not published:
    return None

return time.strftime(
    "%Y-%m-%dT%H:%M:%SZ",
    time.gmtime(published),
)

def _get_source(entry):
"""Extract the publisher name from an RSS entry."""

source = entry.get("source", {})

if isinstance(source, dict):
    source_name = source.get("title")
    if source_name:
        return source_name

# Some feeds include the publisher in the article URL.
link = entry.get("link", "")
hostname = urlparse(link).hostname

if hostname:
    return hostname.removeprefix("www.")

return "Unknown source"

def get_news(categories, limit=DEFAULT_LIMIT):
"""
Fetch news articles for a list of engineering topics.

```
Args:
    categories: A list of search topics or a single topic string.
    limit: Maximum number of articles to return.

Returns:
    A list of dictionaries containing article information.
"""

if isinstance(categories, str):
    categories = [categories]

if not categories:
    return []

# Remove empty topics and duplicate search terms.
topics = list(
    dict.fromkeys(
        topic.strip()
        for topic in categories
        if isinstance(topic, str) and topic.strip()
    )
)

if not topics:
    return []

try:
    limit = int(limit)
except (TypeError, ValueError):
    limit = DEFAULT_LIMIT

limit = max(1, min(limit, MAX_LIMIT))

# Combine related topics into one Google News search.
query = " OR ".join(f'"{topic}"' for topic in topics)

params = {
    "q": query,
    "hl": "en-IN",
    "gl": "IN",
    "ceid": "IN:en",
}

headers = {
    "User-Agent": (
        "StudentEcosystem/1.0 "
        "(student engineering news reader)"
    )
}

try:
    response = requests.get(
        GOOGLE_NEWS_RSS_URL,
        params=params,
        headers=headers,
        timeout=REQUEST_TIMEOUT,
    )

    response.raise_for_status()

    feed = feedparser.parse(response.content)

except requests.RequestException:
    logger.warning("Could not retrieve the Google News RSS feed.")
    return []

if feed.bozo and not feed.entries:
    logger.warning("The Google News RSS feed could not be parsed.")
    return []

articles = []
seen_links = set()

for entry in feed.entries:
    title = entry.get("title", "").strip()
    link = entry.get("link", "").strip()

    # Skip incomplete entries and duplicate articles.
    if not title or not link or link in seen_links:
        continue

    seen_links.add(link)

    articles.append(
        {
            "title": title,
            "link": link,
            "source": _get_source(entry),
            "description": entry.get("summary", ""),
            "published_at": _format_publication_date(entry),
        }
    )

    if len(articles) >= limit:
        break

return articles
