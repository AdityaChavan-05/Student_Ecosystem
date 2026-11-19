"""Student Ecosystem — MIT-WPU student companion.

Flask application exposing a JSON API and a single-page dashboard. The app is
designed to run with zero external configuration: SQLite, an offline campus
guide, a bundled opportunity radar and local AI fallbacks keep every view
usable. Gemini, live RSS and live campus scraping layer on top when available.
"""

from __future__ import annotations

import hashlib
import io
import logging
import os
import re
from datetime import date, datetime, timezone
from email import policy
from email.parser import BytesParser
from pathlib import Path

from flask import Flask, Response, jsonify, redirect, render_template, request, send_from_directory

from ai_summarizer import (
    ai_available,
    generate_briefing,
    summarize_news_batch,
    summarize_notice,
)
from categories import BRANCH_MAPPINGS, get_available_branches
from college_fetcher import get_college_updates, live_status
from config import Config
from database import (
    TASK_PRIORITIES,
    TASK_STATUSES,
    create_summary,
    create_task,
    create_resource,
    delete_bookmark,
    delete_resource,
    delete_summary,
    delete_task,
    get_cached_value,
    get_resource,
    get_settings,
    get_stats,
    get_summary,
    get_task,
    init_db,
    is_database_configured,
    list_bookmarks,
    list_opportunities,
    list_resources,
    list_summaries,
    list_tasks,
    new_id,
    search_all,
    set_cached_value,
    toggle_bookmark,
    update_resource,
    update_settings,
    update_task,
)
from news_fetcher import get_news

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("student-ecosystem")

BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"

app = Flask(
    __name__,
    template_folder=str(TEMPLATES_DIR),
    static_folder=str(STATIC_DIR),
    static_url_path="/static",
)
app.config.from_object(Config)

# Initialise the database at import time so serverless cold starts are fast.
init_db()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def hash_id(prefix: str, value: str) -> str:
    digest = hashlib.sha1((value or "").encode("utf-8", "ignore")).hexdigest()[:12]
    return f"{prefix}{digest}"


def cache_key(prefix: str, *parts) -> str:
    raw = ":".join(str(part) for part in parts)
    return f"{prefix}:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def json_error(message: str, status: int = 400, **extra):
    payload = {"error": message}
    payload.update(extra)
    return jsonify(payload), status


def request_json() -> dict:
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else {}


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def days_left(deadline: str | None) -> int | None:
    if not deadline:
        return None
    try:
        return (date.fromisoformat(deadline[:10]) - date.today()).days
    except ValueError:
        return None


def normalise_tags(value) -> list[str]:
    if isinstance(value, str):
        value = re.split(r"[,\n]", value)
    if not isinstance(value, (list, tuple)):
        return []
    tags = []
    for item in value:
        tag = re.sub(r"\s+", " ", str(item)).strip(" #")[:40]
        if tag and tag not in tags:
            tags.append(tag)
    return tags[:8]


def load_news(branch: str, limit: int, force_refresh: bool = False, query: str = "") -> dict:
    """Fetch + summarise branch news, with caching and graceful degradation."""
    key = cache_key("news", branch, limit)
    if not force_refresh:
        cached = get_cached_value(key)
        if isinstance(cached, dict):
            cached["cached"] = True
            if query:
                lowered = query.lower()
                cached["articles"] = [
                    item
                    for item in cached.get("articles", [])
                    if lowered in (item.get("title", "") + " " + item.get("description", "")).lower()
                    or lowered in " ".join(item.get("tags", [])).lower()
                ]
                cached["count"] = len(cached["articles"])
            return cached

    articles = get_news(branch, limit=limit)
    summaries = summarize_news_batch(articles)

    results = []
    for article, summary in zip(articles, summaries):
        results.append(
            {
                "id": hash_id("news_", article.get("link") or article.get("title", "")),
                "title": article.get("title", ""),
                "link": article.get("link", ""),
                "source": article.get("source", "Engineering publisher"),
                "description": article.get("description", ""),
                "summary": summary.get("tldr", ""),
                "tldr": summary.get("tldr", ""),
                "bullets": summary.get("bullets", []),
                "tags": summary.get("tags") or article.get("tags", []),
                "summary_mode": summary.get("mode", "heuristic"),
                "published_at": article.get("published_at"),
                "fallback": bool(article.get("fallback")),
                "branch": branch,
            }
        )

    payload = {
        "branch": branch,
        "count": len(results),
        "articles": results,
        "ai_mode": "ai" if ai_available() else "heuristic",
        "updated_at": iso_now(),
        "cached": False,
        "query": query,
    }
    set_cached_value(key, payload, ttl_minutes=Config.NEWS_CACHE_MINUTES)
    return payload


def load_campus(limit: int, force_refresh: bool = False, category: str = "", query: str = "") -> dict:
    key = cache_key("campus", limit)
    payload = None
    if not force_refresh:
        cached = get_cached_value(key)
        if isinstance(cached, dict):
            payload = dict(cached)
            payload["cached"] = True

    if payload is None:
        updates = get_college_updates(limit=limit)

        # Enrich the two most substantial live entries with an AI notice summary.
        if ai_available():
            enriched = 0
            for item in updates:
                if enriched >= 2 or item.get("curated"):
                    continue
                body = item.get("description") or ""
                if len(body) < 80:
                    continue
                try:
                    summary = summarize_notice(
                        body,
                        subject=item.get("title", ""),
                        sender=item.get("source", ""),
                    )
                    item["tldr"] = summary.get("tldr") or item.get("tldr")
                    item["what_to_do"] = summary.get("action_items") or item.get("what_to_do")
                    if summary.get("deadlines"):
                        item["deadline"] = summary["deadlines"][0].get("date") or item.get("deadline")
                    if summary.get("urgency"):
                        item["urgency"] = summary["urgency"]
                    enriched += 1
                except Exception:
                    logger.info("Campus AI enrichment failed for %s", item.get("title"))

        for item in updates:
            item["id"] = item.get("id") or hash_id("campus_", item.get("link") or item.get("title", ""))
            left = days_left(item.get("deadline"))
            item["days_left"] = left
            if left is not None and left < 0:
                item["curated"] = item["curated"]
            item["what_to_do"] = item.get("what_to_do") or []
            item["tags"] = item.get("tags") or ["campus"]

        status = live_status(updates)
        categories: dict[str, int] = {}
        for item in updates:
            categories[item["category"]] = categories.get(item["category"], 0) + 1

        payload = {
            "count": len(updates),
            "updates": updates,
            "status": status,
            "categories": categories,
            "college_website_configured": bool(Config.COLLEGE_WEBSITE_URL),
            "college": {
                "name": Config.COLLEGE_NAME,
                "short_name": Config.COLLEGE_SHORT_NAME,
                "city": Config.COLLEGE_CITY,
                "url": Config.COLLEGE_WEBSITE_URL,
            },
            "updated_at": iso_now(),
            "cached": False,
        }
        set_cached_value(key, payload, ttl_minutes=Config.COLLEGE_CACHE_MINUTES)

    if category and category != "All":
        payload["updates"] = [
            item for item in payload.get("updates", []) if item.get("category") == category
        ]
    if query:
        lowered = query.lower()
        payload["updates"] = [
            item
            for item in payload.get("updates", [])
            if lowered
            in (item.get("title", "") + " " + item.get("description", "") + " " + " ".join(item.get("tags", []))).lower()
        ]
    payload["count"] = len(payload.get("updates", []))
    return payload


def decorate_opportunities(items: list[dict]) -> list[dict]:
    saved = {
        bookmark["item_key"]
        for bookmark in list_bookmarks(type_filter="opportunity")
    }
    decorated = []
    for item in items:
        entry = dict(item)
        entry["save_key"] = f"opportunity:{item['id']}"
        entry["saved"] = entry["save_key"] in saved
        entry["days_left"] = days_left(item.get("deadline"))
        entry["deadline_label"] = (
            "Rolling"
            if not item.get("deadline")
            else ("Closed" if (entry["days_left"] or 0) < 0 else f"{entry['days_left']} days left")
        )
        decorated.append(entry)
    return decorated


def build_briefing() -> dict:
    profile = get_settings()
    tasks = [task for task in list_tasks() if task["status"] != "done"][:5]
    # Prefer upcoming campus items so the briefing does not lead with a closed event.
    campus_updates = load_campus(12).get("updates", [])
    upcoming = [item for item in campus_updates if (item.get("days_left") or 0) >= 0]
    upcoming.sort(key=lambda item: str(item.get("deadline") or "9999-12-31"))
    campus = (upcoming or campus_updates)[:3]
    opportunities = decorate_opportunities(list_opportunities(deadline_window="open"))[:3]
    news_cached = get_cached_value(cache_key("news", profile.get("branch", "Computer Science"), 9))
    news = (news_cached or {}).get("articles", [])[:2] if isinstance(news_cached, dict) else []

    context = {
        "student": profile.get("name", "Student"),
        "branch": profile.get("branch", "Computer Science"),
        "date": date.today().isoformat(),
        "tasks": tasks,
        "campus": [
            {"title": item.get("title"), "category": item.get("category"), "deadline": item.get("deadline")}
            for item in campus
        ],
        "opportunities": [
            {"title": item.get("title"), "deadline": item.get("deadline")} for item in opportunities
        ],
        "news": [{"title": item.get("title")} for item in news],
    }
    briefing = generate_briefing(context)
    briefing["generated_at"] = iso_now()
    briefing["context_counts"] = {
        "tasks": len(tasks),
        "campus": len(campus),
        "opportunities": len(opportunities),
        "news": len(news),
    }
    return briefing


def parse_uploaded_notice() -> tuple[str, str, str, str]:
    """Return (text, subject, sender, source) from an uploaded .eml/.txt file."""
    upload = request.files.get("file")
    if not upload or not upload.filename:
        return "", "", "", ""

    filename = upload.filename.lower()
    raw = upload.read(4 * 1024 * 1024)
    if not raw:
        return "", "", "", ""

    if filename.endswith(".eml"):
        try:
            message = BytesParser(policy=policy.default).parsebytes(raw)
            subject = str(message.get("subject", "") or "")
            sender = str(message.get("from", "") or "")
            body = ""
            try:
                part = message.get_body(preferencelist=("plain",))
                if part is not None:
                    body = part.get_content()
            except Exception:
                body = ""
            if not body:
                chunks = []
                for part in message.walk():
                    if part.get_content_type() == "text/plain":
                        try:
                            chunks.append(part.get_content())
                        except Exception:
                            continue
                body = "\n".join(chunks)
            return body[: Config.AI_MAX_INPUT_CHARS], subject, sender, "eml"
        except Exception:
            logger.info("Could not parse .eml upload; treating as text.")

    text = ""
    for encoding in ("utf-8", "utf-16", "latin-1"):
        try:
            text = raw.decode(encoding)
            break
        except (UnicodeDecodeError, LookupError):
            continue
    return text[: Config.AI_MAX_INPUT_CHARS], "", "", "txt"


def strip_email_quotes(text: str) -> str:
    marker = re.split(
        r"\n(?:On .+wrote:|-----Original Message-----|From: .+\nSent:)",
        text,
        maxsplit=1,
    )
    cleaned = marker[0] if marker else text
    return cleaned.strip()


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------

@app.route("/")
def home():
    return render_template("index.html", college_short=Config.COLLEGE_SHORT_NAME)


@app.route("/news")
def news_page():
    return redirect("/#news")


@app.route("/college")
def college_page():
    return redirect("/#campus")


@app.route("/opportunities")
def opportunities_page():
    return redirect("/#opportunities")


@app.route("/mail")
def mail_page():
    return redirect("/#mail")


@app.route("/vault")
def vault_page():
    return redirect("/#vault")


@app.route("/tasks")
def tasks_page():
    return redirect("/#tasks")


@app.route("/favicon.ico")
def favicon():
    return send_from_directory(STATIC_DIR, "favicon.svg", mimetype="image/svg+xml")


@app.route("/manifest.webmanifest")
def manifest():
    payload = {
        "name": "Student Ecosystem — MIT-WPU",
        "short_name": "Ecosystem",
        "description": "Campus updates, opportunities, AI briefings and tasks for MIT-WPU students.",
        "start_url": "/",
        "display": "standalone",
        "background_color": "#f6f7fb",
        "theme_color": "#5b4bff",
        "icons": [
            {
                "src": "/static/favicon.svg",
                "sizes": "any",
                "type": "image/svg+xml",
            }
        ],
    }
    return jsonify(payload)


# ---------------------------------------------------------------------------
# Core API
# ---------------------------------------------------------------------------

@app.get("/api/health")
def health():
    return jsonify(
        {
            "status": "ok",
            "application": "Student Ecosystem",
            "college": Config.COLLEGE_SHORT_NAME,
            "timestamp": iso_now(),
            "database": "sqlite" if is_database_configured() else "unavailable",
            "ai": "configured" if ai_available() else "fallback",
            "model": Config.GEMINI_MODEL,
        }
    )


@app.get("/api/bootstrap")
def bootstrap():
    profile = get_settings()
    branches = get_available_branches()
    if profile.get("branch") not in branches:
        profile["branch"] = branches[0]
    return jsonify(
        {
            "profile": profile,
            "branches": branches,
            "stats": get_stats(),
            "college": {
                "name": Config.COLLEGE_NAME,
                "short_name": Config.COLLEGE_SHORT_NAME,
                "city": Config.COLLEGE_CITY,
                "url": Config.COLLEGE_WEBSITE_URL,
            },
            "features": {
                "ai": ai_available(),
                "ai_mode": "gemini" if ai_available() else "heuristic",
                "model": Config.GEMINI_MODEL,
                "campus_live": bool(Config.COLLEGE_WEBSITE_URL),
            },
            "today": date.today().isoformat(),
            "server_time": iso_now(),
        }
    )


@app.route("/api/profile", methods=["GET", "PATCH", "POST"])
def profile():
    if request.method == "GET":
        return jsonify({"profile": get_settings()})
    patch = request_json()
    if patch.get("branch") and patch["branch"] not in BRANCH_MAPPINGS:
        return json_error("Unsupported engineering branch.")
    updated = update_settings(patch)
    return jsonify({"profile": updated, "stats": get_stats()})


@app.get("/api/branches")
def branches():
    return jsonify({"branches": get_available_branches()})


@app.get("/api/stats")
def stats():
    return jsonify({"stats": get_stats()})


@app.get("/api/news")
def news_api():
    branch = (request.args.get("branch") or get_settings().get("branch") or "Computer Science").strip()
    if branch not in BRANCH_MAPPINGS:
        return json_error("Unsupported engineering branch.", available_branches=get_available_branches())

    try:
        limit = int(request.args.get("limit", Config.DEFAULT_NEWS_LIMIT))
    except (TypeError, ValueError):
        return json_error("The limit must be a number.")
    if not 1 <= limit <= Config.MAX_NEWS_LIMIT:
        return json_error(f"Limit must be between 1 and {Config.MAX_NEWS_LIMIT}.")

    force_refresh = (request.args.get("refresh", "false") or "").lower() == "true"
    query = (request.args.get("q") or "").strip()

    try:
        payload = load_news(branch, limit, force_refresh=force_refresh, query=query)
    except Exception:
        logger.exception("News feed failed.")
        return json_error("The news feed is temporarily unavailable. Please try again.", 503)
    return jsonify(payload)


@app.get("/api/college-updates")
def college_updates_api():
    try:
        limit = int(request.args.get("limit", 12))
    except (TypeError, ValueError):
        return json_error("The limit must be a number.")
    if not 1 <= limit <= 30:
        return json_error("Limit must be between 1 and 30.")

    force_refresh = (request.args.get("refresh", "false") or "").lower() == "true"
    category = (request.args.get("category") or "").strip()
    query = (request.args.get("q") or "").strip()

    try:
        payload = load_campus(limit, force_refresh=force_refresh, category=category, query=query)
    except Exception:
        logger.exception("Campus feed failed.")
        return json_error("Campus updates are temporarily unavailable. Please try again.", 503)
    return jsonify(payload)


@app.get("/api/opportunities")
def opportunities_api():
    track = (request.args.get("track") or "All").strip()
    mode = (request.args.get("mode") or "All").strip()
    deadline = (request.args.get("deadline") or "").strip()
    query = (request.args.get("q") or "").strip()
    saved_only = (request.args.get("saved", "false") or "").lower() == "true"

    items = decorate_opportunities(
        list_opportunities(track=track, mode=mode, deadline_window=deadline, query=query)
    )
    if saved_only:
        items = [item for item in items if item["saved"]]

    tracks = sorted({item["track"] for item in list_opportunities()})
    modes = ["Online", "In-Person", "Hybrid"]

    return jsonify(
        {
            "count": len(items),
            "opportunities": items,
            "tracks": tracks,
            "modes": modes,
            "updated_at": iso_now(),
        }
    )


@app.route("/api/summarize", methods=["POST"])
def summarize_mail():
    data = request_json()
    text = (data.get("text") or "").strip()
    subject = (data.get("subject") or "").strip()
    sender = (data.get("sender") or "").strip()
    source = (data.get("source") or "paste").strip()[:20]

    if request.files:
        file_text, file_subject, file_sender, file_source = parse_uploaded_notice()
        if file_text:
            text = text or file_text
            subject = subject or file_subject
            sender = sender or file_sender
            source = file_source or source

    text = strip_email_quotes(text)
    if len(text) < 20:
        return json_error("Add at least a couple of sentences so we can summarize the notice.", 422)
    if len(text) > Config.AI_MAX_INPUT_CHARS:
        text = text[: Config.AI_MAX_INPUT_CHARS]

    summary = summarize_notice(text, subject=subject, sender=sender)
    saved = create_summary(
        {
            **summary,
            "subject": subject or f"Notice — {date.today().isoformat()}",
            "sender": sender,
            "source": source or "paste",
            "body": text,
        }
    )

    task = None
    if data.get("create_task"):
        title = (summary.get("action_items") or [summary.get("tldr") or "Follow up on notice"])[0]
        due = next(
            (item.get("date") for item in summary.get("deadlines") or [] if item.get("date")),
            "",
        )
        task = create_task(
            {
                "title": title[:200],
                "notes": summary.get("tldr", ""),
                "due_date": due,
                "priority": "high" if summary.get("urgency") in {"high", "urgent"} else "medium",
                "tags": ["mail", *normalise_tags(summary.get("tags"))][:5],
                "source_type": "summary",
                "source_id": saved["id"],
            }
        )

    return jsonify(
        {
            "summary": saved,
            "task": task,
            "ai_mode": summary.get("mode", "heuristic"),
        }
    ), 201


@app.route("/api/summaries", methods=["GET", "POST"])
def summaries():
    if request.method == "POST":
        data = request_json()
        text = (data.get("text") or "").strip()
        if not text:
            return json_error("Notice text is required.", 422)
        summary = summarize_notice(
            text,
            subject=(data.get("subject") or "").strip(),
            sender=(data.get("sender") or "").strip(),
        )
        saved = create_summary(
            {
                **summary,
                "subject": (data.get("subject") or "").strip() or "Untitled notice",
                "sender": (data.get("sender") or "").strip(),
                "source": (data.get("source") or "paste")[:20],
                "body": text,
            }
        )
        return jsonify({"summary": saved}), 201

    query = (request.args.get("q") or "").strip()
    limit = request.args.get("limit", 50)
    try:
        limit = int(limit)
    except (TypeError, ValueError):
        limit = 50
    return jsonify({"count": len(list_summaries(limit=limit, query=query)),
                    "summaries": list_summaries(limit=limit, query=query)})


@app.delete("/api/summaries/<summary_id>")
def remove_summary(summary_id: str):
    if not delete_summary(summary_id):
        return json_error("Summary not found.", 404)
    return jsonify({"deleted": True, "id": summary_id})


@app.post("/api/summaries/<summary_id>/task")
def summary_to_task(summary_id: str):
    summary = get_summary(summary_id)
    if not summary:
        return json_error("Summary not found.", 404)
    data = request_json()
    action = (data.get("title") or (summary.get("action_items") or ["Follow up on notice"])[0])[:200]
    due = data.get("due_date") or next(
        (item.get("date") for item in summary.get("deadlines") or [] if item.get("date")),
        "",
    )
    task = create_task(
        {
            "title": action,
            "notes": summary.get("tldr", ""),
            "due_date": due,
            "priority": "high" if summary.get("urgency") in {"high", "urgent"} else "medium",
            "tags": ["mail", *normalise_tags(summary.get("tags"))][:5],
            "source_type": "summary",
            "source_id": summary_id,
        }
    )
    return jsonify({"task": task}), 201


@app.get("/api/tasks")
def tasks():
    status = (request.args.get("status") or "").strip()
    priority = (request.args.get("priority") or "").strip()
    query = (request.args.get("q") or "").strip()
    items = list_tasks(status=status, priority=priority, query=query)
    counts = {"todo": 0, "doing": 0, "done": 0}
    for item in list_tasks():
        counts[item["status"]] = counts.get(item["status"], 0) + 1
    return jsonify({"count": len(items), "tasks": items, "counts": counts, "stats": get_stats()})


@app.post("/api/tasks")
def add_task():
    data = request_json()
    if not (data.get("title") or "").strip():
        return json_error("A task title is required.", 422)
    data["tags"] = normalise_tags(data.get("tags"))
    task = create_task(data)
    return jsonify({"task": task, "stats": get_stats()}), 201


@app.route("/api/tasks/<task_id>", methods=["PATCH", "POST", "DELETE"])
def task_detail(task_id: str):
    if request.method == "DELETE":
        if not delete_task(task_id):
            return json_error("Task not found.", 404)
        return jsonify({"deleted": True, "id": task_id, "stats": get_stats()})
    patch = request_json()
    if not patch:
        return json_error("No task changes were provided.", 422)
    if "status" in patch and str(patch.get("status", "")).lower() not in TASK_STATUSES:
        return json_error("Status must be one of: todo, doing, done.", 422)
    if "priority" in patch and str(patch.get("priority", "")).lower() not in TASK_PRIORITIES:
        return json_error("Priority must be one of: low, medium, high, urgent.", 422)
    if "title" in patch and not str(patch.get("title", "")).strip():
        return json_error("A task title cannot be empty.", 422)
    if "tags" in patch:
        patch["tags"] = normalise_tags(patch.get("tags"))
    task = update_task(task_id, patch)
    if not task:
        return json_error("Task not found.", 404)
    return jsonify({"task": task, "stats": get_stats()})


@app.get("/api/vault")
def vault():
    branch = (request.args.get("branch") or "").strip()
    subject = (request.args.get("subject") or "").strip()
    type_filter = (request.args.get("type") or "").strip()
    query = (request.args.get("q") or "").strip()
    items = list_resources(
        subject=subject, branch=branch, type_filter=type_filter, query=query
    )
    subjects = sorted({item["subject"] for item in list_resources()})
    types = sorted({item["type"] for item in list_resources()})
    return jsonify(
        {
            "count": len(items),
            "resources": items,
            "subjects": subjects,
            "types": types,
            "stats": get_stats(),
        }
    )


@app.post("/api/vault")
def add_resource_api():
    data = request_json()
    if not (data.get("title") or "").strip():
        return json_error("A resource title is required.", 422)
    data["tags"] = normalise_tags(data.get("tags"))
    resource = create_resource(data)
    return jsonify({"resource": resource, "stats": get_stats()}), 201


@app.route("/api/vault/<resource_id>", methods=["PATCH", "POST", "DELETE"])
def resource_detail(resource_id: str):
    if request.method == "DELETE":
        if not delete_resource(resource_id):
            return json_error("Resource not found.", 404)
        return jsonify({"deleted": True, "id": resource_id, "stats": get_stats()})
    patch = request_json()
    if "tags" in patch:
        patch["tags"] = normalise_tags(patch.get("tags"))
    resource = update_resource(resource_id, patch)
    if not resource:
        return json_error("Resource not found.", 404)
    return jsonify({"resource": resource, "stats": get_stats()})


@app.get("/api/bookmarks")
def bookmarks():
    type_filter = (request.args.get("type") or "").strip()
    query = (request.args.get("q") or "").strip()
    items = list_bookmarks(type_filter=type_filter, query=query)
    return jsonify({"count": len(items), "bookmarks": items})


@app.post("/api/bookmarks")
def bookmark_toggle():
    data = request_json()
    if not (data.get("item_key") or "").strip():
        return json_error("item_key is required.", 422)
    try:
        result = toggle_bookmark(data)
    except ValueError as error:
        return json_error(str(error), 422)
    result["stats"] = get_stats()
    return jsonify(result)


@app.delete("/api/bookmarks/<bookmark_id>")
def bookmark_delete(bookmark_id: str):
    if not delete_bookmark(bookmark_id):
        return json_error("Bookmark not found.", 404)
    return jsonify({"deleted": True, "id": bookmark_id, "stats": get_stats()})


@app.get("/api/briefing")
def briefing():
    force = (request.args.get("refresh", "false") or "").lower() == "true"
    if force:
        # Bust the briefing cache by computing a fresh result from live context.
        cached_news = get_cached_value(
            cache_key("news", get_settings().get("branch", "Computer Science"), 9)
        )
        if not cached_news:
            load_news(get_settings().get("branch", "Computer Science"), 9)
        result = build_briefing()
        return jsonify({"briefing": result, "stats": get_stats()})
    result = build_briefing()
    return jsonify({"briefing": result, "stats": get_stats()})


@app.get("/api/search")
def search():
    query = (request.args.get("q") or "").strip()
    if len(query) < 2:
        return jsonify(
            {
                "query": query,
                "tasks": [],
                "summaries": [],
                "vault": [],
                "opportunities": [],
                "bookmarks": [],
            }
        )
    return jsonify({"query": query, **search_all(query)})


@app.get("/api/notifications")
def notifications():
    """A compact digest used by the header bell."""
    tasks = list_tasks()
    due = [task for task in tasks if task["status"] != "done" and task.get("due_date")][:5]
    stats = get_stats()
    items = [
        {
            "type": "task",
            "title": task["title"],
            "subtitle": f"Due {task['due_date']}" if task.get("due_date") else "No due date",
            "priority": task.get("priority", "medium"),
            "due_date": task.get("due_date"),
        }
        for task in due
    ]
    return jsonify({"count": len(items), "items": items, "stats": stats})


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------

@app.after_request
def add_cors_headers(response):
    origin = request.headers.get("Origin", "")
    allowed = Config.CORS_ORIGINS
    if origin and ("*" in allowed or origin in allowed):
        response.headers["Access-Control-Allow-Origin"] = "*" if "*" in allowed else origin
        response.headers["Vary"] = "Origin"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, PATCH, DELETE, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, Accept"
        response.headers["Access-Control-Max-Age"] = "86400"
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    return response


@app.errorhandler(404)
def not_found(error):
    if request.path.startswith("/api/"):
        return json_error("API endpoint not found.", 404)
    return render_template("index.html", college_short=Config.COLLEGE_SHORT_NAME), 404


@app.errorhandler(413)
def too_large(error):
    return json_error("The uploaded file is too large. Maximum size is 6 MB.", 413)


@app.errorhandler(500)
def server_error(error):
    logger.exception("Unhandled application error: %s", error)
    if request.path.startswith("/api/"):
        return json_error("An unexpected server error occurred.", 500)
    return render_template("index.html", college_short=Config.COLLEGE_SHORT_NAME), 500


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=Config.PORT,
        debug=Config.DEBUG,
    )
