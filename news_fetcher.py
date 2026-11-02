import logging
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html import unescape
from urllib.parse import quote

import feedparser
import requests
from bs4 import BeautifulSoup

from categories import BRANCH_MAPPINGS, GENERAL_CATEGORIES

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT = 10
DEFAULT_LIMIT = 10

GOOGLE_NEWS_URL = (
"https://news.google.com/rss/search"
"?q={query}&hl=en-IN&gl=IN&ceid=IN:en"
)

BING_NEWS_URL = (
"https://www.bing.com/news/search"
"?q={query}&format=rss&setlang=en-in"
)

session = requests.Session()

session.headers.update({
"User-Agent": (
"Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
"AppleWebKit/537.36 Chrome/120.0 Safari/537.36"
)
})

def clean_text(text):
"""Remove HTML tags and clean article descriptions."""

    if not text:
        return ""

soup = BeautifulSoup(unescape(text), "html.parser")

return " ".join(soup.get_text(" ", strip=True).split())

def parse_date(date_string):
"""Convert publication dates into UTC ISO format."""

if not date_string:
    return None

try:
    published = parsedate_to_datetime(date_string)

    if published.tzinfo is None:
        published = published.replace(tzinfo=timezone.utc)

    return published.astimezone(timezone.utc).isoformat()

except (TypeError, ValueError, OverflowError):
    return None

def fetch_rss(url):
"""Download and parse an RSS feed safely."""

try:
    response = session.get(
        url,
        timeout=REQUEST_TIMEOUT
    )

    response.raise_for_status()

    feed = feedparser.parse(response.content)

    if not feed.entries:
        logger.warning("RSS source returned no articles.")
        return []

    articles = []

    for entry in feed.entries:

        title = entry.get("title", "").strip()
        link = entry.get("link", "").strip()

        if not title or not link:
            continue

        source_info = entry.get("source", {})
        source = source_info.get("title", "")

        description = clean_text(
            entry.get("summary", "")
        )

        published = entry.get("published", "")

        articles.append({
            "title": title,
            "link": link,
            "url": link,
            "source": source or "News Publisher",
            "description": description,
            "content": description,
            "published_at": parse_date(published),
        })

    return articles

except requests.RequestException as error:
    logger.warning("RSS request failed: %s", error)
    return []

except Exception:
    logger.exception("Unexpected RSS parsing error.")
    return []

def get_news(branch="Computer Science", limit=DEFAULT_LIMIT):
"""
Fetch branch-specific engineering news.

Google News is the primary source.
Bing News RSS is the backup source.

Supports either a branch name or a list of topics.
"""

try:
    limit = max(1, min(int(limit), 30))
except (TypeError, ValueError):
    limit = DEFAULT_LIMIT

# Support both branch names and topic lists.
if isinstance(branch, list):
    branch_name = "Engineering"
    topics = branch

else:
    if not isinstance(branch, str):
        branch = "Computer Science"

    branch = branch.strip()

    if branch not in BRANCH_MAPPINGS:
        branch = "Computer Science"

    branch_name = branch
    topics = BRANCH_MAPPINGS.get(branch, [])

# Add general engineering opportunities.
topics = list(dict.fromkeys(topics + GENERAL_CATEGORIES))

# Construct one combined search instead of many requests.
search_terms = [
    f'"{topic}"'
    for topic in topics
    if isinstance(topic, str) and topic.strip()
]

if not search_terms:
    return []

query = " OR ".join(search_terms)

encoded_query = quote(query, safe="")

# First attempt: Google News.
google_url = GOOGLE_NEWS_URL.format(
    query=encoded_query
)

articles = fetch_rss(google_url)

# Second attempt: Bing News, if Google didn't return enough.
if len(articles) < limit:

    bing_url = BING_NEWS_URL.format(
        query=encoded_query
    )

    backup_articles = fetch_rss(bing_url)

    articles.extend(backup_articles)

# Remove duplicate articles.
unique_articles = []
seen_links = set()

for article in articles:

    link = article.get("url", "").strip()

    if not link or link in seen_links:
        continue

    seen_links.add(link)

    article["branch"] = branch_name

    unique_articles.append(article)

    if len(unique_articles) >= limit:
        break

logger.info(
    "Fetched %d articles for %s",
    len(unique_articles),
    branch_name
)

return unique_articles
