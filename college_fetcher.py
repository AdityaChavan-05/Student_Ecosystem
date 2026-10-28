import logging
import os
import re

from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(**name**)

REQUEST_TIMEOUT = 12
DEFAULT_LIMIT = 10

KEYWORDS = {
"Examination": [
"exam",
"examination",
"timetable",
"time-table",
"hall ticket",
"admit card",
"results",
],
"Notice": [
"notice",
"announcement",
"circular",
"notification",
"important information",
],
"Event": [
"event",
"fest",
"workshop",
"seminar",
"conference",
"competition",
"hackathon",
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
],
}

def _classify_update(text):
"""Identify the likely category of a college update."""

```
text = text.lower()

for category, keywords in KEYWORDS.items():
    if any(keyword in text for keyword in keywords):
        return category

return "General"
```

def _is_same_website(url, base_url):
"""Allow links belonging to the configured college website."""

```
try:
    target = urlparse(url)
    base = urlparse(base_url)

    return (
        target.scheme in {"http", "https"}
        and target.hostname is not None
        and target.hostname.lower() == (base.hostname or "").lower()
    )

except ValueError:
    return False
```

def get_college_updates(base_url=None, limit=DEFAULT_LIMIT):
"""
Discover relevant college updates from the official homepage.

```
Args:
    base_url: College website homepage.
              Defaults to COLLEGE_WEBSITE_URL.
    limit: Maximum number of updates to return.

Returns:
    A list of dictionaries containing update information.

Note:
    This starter scraper discovers relevant links on the
    homepage. It does not yet extract notices from every
    linked page or download PDF contents.
"""

base_url = (
    base_url or os.getenv("COLLEGE_WEBSITE_URL", "")
).strip()

if not base_url:
    logger.warning(
        "College website URL is not configured."
    )
    return []

try:
    limit = int(limit)
except (TypeError, ValueError):
    limit = DEFAULT_LIMIT

limit = max(1, min(limit, 30))

parsed_base = urlparse(base_url)

if (
    parsed_base.scheme not in {"http", "https"}
    or not parsed_base.hostname
    or parsed_base.username
    or parsed_base.password
):
    logger.warning("The configured college URL is invalid.")
    return []

headers = {
    "User-Agent": (
        "StudentEcosystem/1.0 "
        "(college notice discovery)"
    )
}

try:
    response = requests.get(
        base_url,
        headers=headers,
        timeout=REQUEST_TIMEOUT,
    )

    response.raise_for_status()

    # Follow redirects only if they remain on the same website.
    if not _is_same_website(response.url, base_url):
        logger.warning(
            "The college website redirected to another host."
        )
        return []

    content_type = response.headers.get(
        "Content-Type", ""
    ).lower()

    if "html" not in content_type:
        logger.warning(
            "The configured college homepage is not HTML."
        )
        return []

except requests.RequestException:
    logger.warning(
        "Could not retrieve the college homepage."
    )
    return []

soup = BeautifulSoup(response.text, "html.parser")

# Remove elements that do not provide useful page content.
for element in soup(
    ["script", "style", "noscript", "svg"]
):
    element.decompose()

updates = []
seen_links = set()

for anchor in soup.find_all("a", href=True):
    title = anchor.get_text(" ", strip=True)
    href = anchor.get("href", "").strip()

    if not title or not href:
        continue

    # Ignore navigation fragments and non-web links.
    if href.startswith(
        ("#", "mailto:", "tel:", "javascript:")
    ):
        continue

    absolute_url = urljoin(response.url, href)

    if not _is_same_website(absolute_url, response.url):
        continue

    if absolute_url in seen_links:
        continue

    # Include both the link title and URL when classifying.
    searchable_text = f"{title} {absolute_url}"
    category = _classify_update(searchable_text)

    if category == "General":
        continue

    # Use surrounding text as a brief description when available.
    parent = anchor.find_parent(["li", "article", "tr", "div"])

    description = ""

    if parent:
        description = parent.get_text(" ", strip=True)

    if not description:
        description = title

    # Keep descriptions concise.
    description = re.sub(
        r"\s+", " ", description
    ).strip()[:500]

    seen_links.add(absolute_url)

    updates.append(
        {
            "title": title,
            "link": absolute_url,
            "source": parsed_base.hostname,
            "description": description,
            "category": category,
            "published_at": None,
        }
    )

    if len(updates) >= limit:
        break

return updates
```
