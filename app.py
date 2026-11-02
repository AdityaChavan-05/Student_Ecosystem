import hashlib
import logging
import os
from datetime import datetime, timezone

from flask import Flask, Response, jsonify, request, send_from_directory

from ai_summarizer import summarize_news
from categories import BRANCH_MAPPINGS, GENERAL_CATEGORIES, get_available_branches
from college_fetcher import get_college_updates
from config import Config
from database import get_cached_value, set_cached_value
from data_cleaner import clean_article_text, limit_text
from news_fetcher import get_news

# All dashboard HTML, CSS and JavaScript are stored in this Python module.
from frontend import INDEX_HTML, STYLE_CSS, SCRIPT_JS

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")

app = Flask(__name__)
app.config.from_object(Config)


def make_cache_key(prefix, value):
    digest = hashlib.sha256(f"{prefix}:{value}".encode("utf-8")).hexdigest()
    return f"{prefix}:{digest}"


def get_cache_ttl(setting_name, default):
    try:
        return max(1, int(getattr(Config, setting_name, default)))
    except (TypeError, ValueError):
        return default


@app.route("/")
def home():
    return Response(INDEX_HTML, mimetype="text/html")


@app.route("/style.css")
def public_stylesheet():
    return Response(STYLE_CSS, mimetype="text/css")


@app.route("/script.js")
def public_script():
    return Response(SCRIPT_JS, mimetype="application/javascript")


# Keep these pages in your existing frontend folder.
@app.route("/news")
def news_page():
    return send_from_directory(FRONTEND_DIR, "news.html")


@app.route("/college")
def college_page():
    return send_from_directory(FRONTEND_DIR, "college.html")


@app.route("/api/health")
def health():
    return jsonify({
        "status": "ok",
        "application": "Student Ecosystem",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })


@app.route("/api/branches")
def branches():
    return jsonify({"branches": get_available_branches()})


@app.route("/api/news")
def news_api():
    branch = request.args.get("branch", "Artificial Intelligence").strip()
    if branch not in BRANCH_MAPPINGS:
        return jsonify({
            "error": "Unsupported engineering branch.",
            "available_branches": get_available_branches(),
        }), 400

    try:
        limit = int(request.args.get("limit", Config.DEFAULT_NEWS_LIMIT))
    except (TypeError, ValueError):
        return jsonify({"error": "The limit must be a number."}), 400

    if not 1 <= limit <= Config.MAX_NEWS_LIMIT:
        return jsonify({
            "error": f"Limit must be between 1 and {Config.MAX_NEWS_LIMIT}."
        }), 400

    force_refresh = request.args.get("refresh", "false").lower() == "true"
    topics = BRANCH_MAPPINGS[branch] + GENERAL_CATEGORIES
    cache_key = make_cache_key("news", f"{branch}:{limit}")

    if not force_refresh:
        cached_data = get_cached_value(cache_key)
        if cached_data is not None:
            return jsonify(cached_data)

    articles = get_news(topics, limit=limit)
    results = []

    for article in articles:
        raw_description = article.get("description", "")
        clean_description = limit_text(
            clean_article_text(raw_description),
            max_chars=5000,
        )
        summary = summarize_news(
            clean_description or article.get("title", "")
        )
        results.append({
            "title": article.get("title", ""),
            "link": article.get("link", ""),
            "source": article.get("source", "Unknown source"),
            "description": clean_description,
            "summary": summary,
            "published_at": article.get("published_at"),
        })

    payload = {
        "branch": branch,
        "count": len(results),
        "articles": results,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    set_cached_value(
        cache_key,
        payload,
        ttl_minutes=get_cache_ttl("NEWS_CACHE_MINUTES", 30),
    )
    return jsonify(payload)


@app.route("/api/college-updates")
def college_updates_api():
    try:
        limit = int(request.args.get("limit", 10))
    except (TypeError, ValueError):
        return jsonify({"error": "The limit must be a number."}), 400

    if not 1 <= limit <= 30:
        return jsonify({"error": "Limit must be between 1 and 30."}), 400

    college_url = os.getenv("COLLEGE_WEBSITE_URL", "").strip()
    if not college_url:
        return jsonify({
            "college_website_configured": False,
            "message": (
                "College updates will be available after the official "
                "college website has been configured."
            ),
            "count": 0,
            "updates": [],
        })

    cache_key = make_cache_key("college", f"{college_url}:{limit}")
    cached_data = get_cached_value(cache_key)
    if cached_data is not None:
        return jsonify(cached_data)

    updates = get_college_updates(base_url=college_url, limit=limit)
    payload = {
        "college_website_configured": True,
        "count": len(updates),
        "updates": updates,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    set_cached_value(
        cache_key,
        payload,
        ttl_minutes=get_cache_ttl("COLLEGE_CACHE_MINUTES", 15),
    )
    return jsonify(payload)


@app.errorhandler(404)
def not_found(error):
    if request.path.startswith("/api/"):
        return jsonify({"error": "API endpoint not found."}), 404
    return error


@app.errorhandler(500)
def internal_server_error(error):
    logger.exception("An unexpected application error occurred: %s", error)
    return jsonify({"error": "An internal server error occurred."}), 500


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.getenv("PORT", "5000")),
        debug=Config.DEBUG,
    )
