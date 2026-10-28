import hashlib
import logging
import os
from datetime import datetime, timezone

from flask import Flask, jsonify, request, send_from_directory

from ai_summarizer import summarize_news
from categories import (
BRANCH_MAPPINGS,
GENERAL_CATEGORIES,
get_available_branches,
)
from college_fetcher import get_college_updates
from config import Config
from database import get_cached_value, set_cached_value
from data_cleaner import clean_article_text, limit_text
from news_fetcher import get_news

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(**name**)

BASE_DIR = os.path.dirname(os.path.abspath(**file**))
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")

app = Flask(
**name**,
static_folder=FRONTEND_DIR,
static_url_path="/static",
)

app.config.from_object(Config)

def make_cache_key(prefix, value):
"""Create a consistent cache key for a request."""
serialized = f"{prefix}:{value}"

```
digest = hashlib.sha256(
    serialized.encode("utf-8")
).hexdigest()

return f"{prefix}:{digest}"
```

def get_cache_ttl(setting_name, default):
"""Read a positive cache duration from configuration."""
try:
value = int(getattr(Config, setting_name, default))
return max(1, value)
except (TypeError, ValueError):
return default

@app.route("/")
def home():
"""Serve the main website homepage."""
return send_from_directory(FRONTEND_DIR, "index.html")

@app.route("/news")
def news_page():
"""Serve the global news page."""
return send_from_directory(FRONTEND_DIR, "news.html")

@app.route("/college")
def college_page():
"""Serve the college updates page."""
return send_from_directory(FRONTEND_DIR, "college.html")

@app.route("/api/health")
def health():
"""Simple health check for deployment monitoring."""
return jsonify(
{
"status": "ok",
"application": "Student Ecosystem",
"timestamp": datetime.now(timezone.utc).isoformat(),
}
)

@app.route("/api/branches")
def branches():
"""Return the supported engineering branches."""
return jsonify(
{
"branches": get_available_branches(),
}
)

@app.route("/api/news")
def news_api():
"""
Return cached, branch-specific news and AI summaries.

```
Query parameters:
    branch: Engineering branch.
    limit: Number of articles, from 1 to 10.
    refresh: Set to true to bypass the existing cache.
"""
branch = request.args.get(
    "branch",
    "Artificial Intelligence",
).strip()

if branch not in BRANCH_MAPPINGS:
    return jsonify(
        {
            "error": "Unsupported engineering branch.",
            "available_branches": get_available_branches(),
        }
    ), 400

try:
    limit = int(
        request.args.get(
            "limit",
            Config.DEFAULT_NEWS_LIMIT,
        )
    )
except (TypeError, ValueError):
    return jsonify(
        {"error": "The limit must be a number."}
    ), 400

if not 1 <= limit <= Config.MAX_NEWS_LIMIT:
    return jsonify(
        {
            "error": (
                f"Limit must be between 1 and "
                f"{Config.MAX_NEWS_LIMIT}."
            )
        }
    ), 400

force_refresh = (
    request.args.get("refresh", "false").lower()
    == "true"
)

topics = BRANCH_MAPPINGS[branch] + GENERAL_CATEGORIES

cache_key = make_cache_key(
    "news",
    f"{branch}:{limit}",
)

if not force_refresh:
    cached_data = get_cached_value(cache_key)

    if cached_data is not None:
        return jsonify(cached_data)

articles = get_news(
    topics,
    limit=limit,
)

results = []

for article in articles:
    raw_description = article.get("description", "")

    clean_description = limit_text(
        clean_article_text(raw_description),
        max_chars=5000,
    )

    summary = summarize_news(
        clean_description
        or article.get("title", "")
    )

    results.append(
        {
            "title": article.get("title", ""),
            "link": article.get("link", ""),
            "source": article.get("source", "Unknown source"),
            "description": clean_description,
            "summary": summary,
            "published_at": article.get("published_at"),
        }
    )

payload = {
    "branch": branch,
    "count": len(results),
    "articles": results,
    "updated_at": datetime.now(timezone.utc).isoformat(),
}

# Store results only when Supabase has been configured.
ttl = get_cache_ttl("NEWS_CACHE_MINUTES", 30)

set_cached_value(
    cache_key,
    payload,
    ttl_minutes=ttl,
)

return jsonify(payload)
```

@app.route("/api/college-updates")
def college_updates_api():
"""
Return college updates from the configured official website.

```
The college website is optional. If it is not configured,
return an empty list instead of using a dummy website.
"""
try:
    limit = int(request.args.get("limit", 10))
except (TypeError, ValueError):
    return jsonify(
        {"error": "The limit must be a number."}
    ), 400

if not 1 <= limit <= 30:
    return jsonify(
        {"error": "Limit must be between 1 and 30."}
    ), 400

college_url = os.getenv(
    "COLLEGE_WEBSITE_URL",
    "",
).strip()

if not college_url:
    return jsonify(
        {
            "college_website_configured": False,
            "message": (
                "College updates will be available "
                "after the official college website "
                "has been configured."
            ),
            "count": 0,
            "updates": [],
        }
    )

cache_key = make_cache_key(
    "college",
    f"{college_url}:{limit}",
)

cached_data = get_cached_value(cache_key)

if cached_data is not None:
    return jsonify(cached_data)

updates = get_college_updates(
    base_url=college_url,
    limit=limit,
)

payload = {
    "college_website_configured": True,
    "count": len(updates),
    "updates": updates,
    "updated_at": datetime.now(timezone.utc).isoformat(),
}

ttl = get_cache_ttl("COLLEGE_CACHE_MINUTES", 15)

set_cached_value(
    cache_key,
    payload,
    ttl_minutes=ttl,
)

return jsonify(payload)
```

@app.errorhandler(404)
def not_found(error):
"""Return a clear JSON response for missing API routes."""
if request.path.startswith("/api/"):
return jsonify(
{"error": "API endpoint not found."}
), 404

```
return error
```

@app.errorhandler(500)
def internal_server_error(error):
"""Avoid exposing internal exception details."""
logger.exception("An unexpected application error occurred.")

```
return jsonify(
    {"error": "An internal server error occurred."}
), 500
```

if **name** == "**main**":
app.run(
host="0.0.0.0",
port=int(os.getenv("PORT", "5000")),
debug=Config.DEBUG,
)
