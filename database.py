"""Local-first persistence for Student Ecosystem.

SQLite is used by default so the application works with zero configuration.
The module keeps the public surface intentionally small: cache helpers used by
the fetchers plus CRUD helpers for summaries, tasks, the academic vault,
bookmarks and the opportunities radar.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
import uuid
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from config import Config

logger = logging.getLogger(__name__)

DB_PATH = Path(Config.DATABASE_PATH)
_DB_LOCK = threading.Lock()
_INITIALISED = False


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def today() -> date:
    return datetime.now(timezone.utc).date()


def new_id(prefix: str = "") -> str:
    raw = uuid.uuid4().hex[:12]
    return f"{prefix}{raw}" if prefix else raw


def _json(value, default):
    if value is None or value == "":
        return default
    if isinstance(value, (list, dict)):
        return value
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return default


def _dumps(value) -> str:
    return json.dumps(value, ensure_ascii=False)


@contextmanager
def get_connection():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH, timeout=15)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA foreign_keys=ON")
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def _rows(cursor) -> list[dict]:
    return [dict(row) for row in cursor.fetchall()]


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

SCHEMA = """
CREATE TABLE IF NOT EXISTS app_cache (
    cache_key  TEXT PRIMARY KEY,
    value      TEXT NOT NULL,
    expires_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS summaries (
    id           TEXT PRIMARY KEY,
    subject      TEXT NOT NULL DEFAULT '',
    sender       TEXT NOT NULL DEFAULT '',
    source       TEXT NOT NULL DEFAULT 'paste',
    category     TEXT NOT NULL DEFAULT 'General',
    urgency      TEXT NOT NULL DEFAULT 'normal',
    tldr         TEXT NOT NULL DEFAULT '',
    action_items TEXT NOT NULL DEFAULT '[]',
    deadlines    TEXT NOT NULL DEFAULT '[]',
    tags         TEXT NOT NULL DEFAULT '[]',
    body         TEXT NOT NULL DEFAULT '',
    mode         TEXT NOT NULL DEFAULT 'heuristic',
    created_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS tasks (
    id          TEXT PRIMARY KEY,
    title       TEXT NOT NULL,
    notes       TEXT NOT NULL DEFAULT '',
    due_date    TEXT NOT NULL DEFAULT '',
    priority    TEXT NOT NULL DEFAULT 'medium',
    status      TEXT NOT NULL DEFAULT 'todo',
    tags        TEXT NOT NULL DEFAULT '[]',
    source_type TEXT NOT NULL DEFAULT 'manual',
    source_id   TEXT NOT NULL DEFAULT '',
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL,
    completed_at TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS vault (
    id          TEXT PRIMARY KEY,
    title       TEXT NOT NULL,
    subject     TEXT NOT NULL DEFAULT 'General',
    branch      TEXT NOT NULL DEFAULT 'All',
    type        TEXT NOT NULL DEFAULT 'link',
    url         TEXT NOT NULL DEFAULT '',
    description TEXT NOT NULL DEFAULT '',
    tags        TEXT NOT NULL DEFAULT '[]',
    starred     INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS bookmarks (
    id         TEXT PRIMARY KEY,
    item_key   TEXT NOT NULL UNIQUE,
    type       TEXT NOT NULL,
    title      TEXT NOT NULL DEFAULT '',
    subtitle   TEXT NOT NULL DEFAULT '',
    url        TEXT NOT NULL DEFAULT '',
    payload    TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS opportunities (
    id             TEXT PRIMARY KEY,
    title          TEXT NOT NULL,
    organizer      TEXT NOT NULL DEFAULT '',
    description    TEXT NOT NULL DEFAULT '',
    why            TEXT NOT NULL DEFAULT '',
    track          TEXT NOT NULL DEFAULT 'Hackathon',
    mode           TEXT NOT NULL DEFAULT 'Online',
    location       TEXT NOT NULL DEFAULT '',
    deadline       TEXT NOT NULL DEFAULT '',
    starts_at      TEXT NOT NULL DEFAULT '',
    prize          TEXT NOT NULL DEFAULT '',
    perks          TEXT NOT NULL DEFAULT '',
    url            TEXT NOT NULL DEFAULT '',
    tags           TEXT NOT NULL DEFAULT '[]',
    recurrence_days INTEGER NOT NULL DEFAULT 365,
    source         TEXT NOT NULL DEFAULT 'curated',
    created_at     TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_tasks_due ON tasks(due_date);
CREATE INDEX IF NOT EXISTS idx_summaries_created ON summaries(created_at);
CREATE INDEX IF NOT EXISTS idx_bookmarks_type ON bookmarks(type);
CREATE INDEX IF NOT EXISTS idx_vault_subject ON vault(subject);
"""


def init_db() -> None:
    """Create tables and seed first-run content (idempotent)."""
    global _INITIALISED
    with _DB_LOCK:
        if _INITIALISED:
            return
        with get_connection() as connection:
            connection.executescript(SCHEMA)
        _INITIALISED = True

    # Imported lazily to avoid a circular import at module load time.
    try:
        from seed_data import seed_vault, seed_opportunities

        seed_vault()
        seed_opportunities()
    except Exception:  # pragma: no cover - seeding must never break boot
        logger.exception("Seeding first-run content failed.")


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------

def get_cached_value(cache_key: str):
    if not cache_key:
        return None
    init_db()
    try:
        with get_connection() as connection:
            row = connection.execute(
                "SELECT value FROM app_cache WHERE cache_key = ? AND expires_at > ?",
                (str(cache_key), utcnow()),
            ).fetchone()
        if not row:
            return None
        return _json(row["value"], None)
    except Exception:
        logger.warning("Could not read the application cache.", exc_info=True)
        return None


def set_cached_value(cache_key: str, value, ttl_minutes: int = 30) -> bool:
    if not cache_key:
        return False
    init_db()
    try:
        ttl_minutes = max(1, int(ttl_minutes))
        expires = (
            datetime.now(timezone.utc) + timedelta(minutes=ttl_minutes)
        ).isoformat(timespec="seconds")
        with get_connection() as connection:
            connection.execute(
                """
                INSERT INTO app_cache (cache_key, value, expires_at)
                VALUES (?, ?, ?)
                ON CONFLICT(cache_key) DO UPDATE SET
                    value = excluded.value,
                    expires_at = excluded.expires_at
                """,
                (str(cache_key), _dumps(value), expires),
            )
        return True
    except Exception:
        logger.warning("Could not write the application cache.", exc_info=True)
        return False


def purge_expired_cache() -> int:
    init_db()
    try:
        with get_connection() as connection:
            cursor = connection.execute(
                "DELETE FROM app_cache WHERE expires_at <= ?", (utcnow(),)
            )
            return cursor.rowcount or 0
    except Exception:
        return 0


def is_database_configured() -> bool:
    """The local SQLite database is always available."""
    return True


# ---------------------------------------------------------------------------
# Settings / profile
# ---------------------------------------------------------------------------

DEFAULT_PROFILE = {
    "name": "MIT-WPU Student",
    "branch": "Computer Science",
    "year": "3rd Year",
    "semester": "Semester 5",
    "email": "",
    "goal": "Land a strong internship while keeping academics on track",
}


def get_settings() -> dict:
    init_db()
    values = dict(DEFAULT_PROFILE)
    try:
        with get_connection() as connection:
            rows = connection.execute("SELECT key, value FROM settings").fetchall()
        for row in rows:
            values[row["key"]] = row["value"]
    except Exception:
        logger.warning("Could not read settings.", exc_info=True)
    return values


def update_settings(patch: dict) -> dict:
    init_db()
    allowed = set(DEFAULT_PROFILE)
    try:
        with get_connection() as connection:
            for key, value in (patch or {}).items():
                if key not in allowed:
                    continue
                connection.execute(
                    """
                    INSERT INTO settings (key, value) VALUES (?, ?)
                    ON CONFLICT(key) DO UPDATE SET value = excluded.value
                    """,
                    (key, str(value or "")),
                )
    except Exception:
        logger.warning("Could not save settings.", exc_info=True)
    return get_settings()


# ---------------------------------------------------------------------------
# Summaries
# ---------------------------------------------------------------------------

def _summary_row(row: dict) -> dict:
    return {
        "id": row["id"],
        "subject": row["subject"],
        "sender": row["sender"],
        "source": row["source"],
        "category": row["category"],
        "urgency": row["urgency"],
        "tldr": row["tldr"],
        "action_items": _json(row["action_items"], []),
        "deadlines": _json(row["deadlines"], []),
        "tags": _json(row["tags"], []),
        "body": row["body"],
        "mode": row["mode"],
        "created_at": row["created_at"],
    }


def create_summary(data: dict) -> dict:
    init_db()
    record = {
        "id": new_id("sum_"),
        "subject": (data.get("subject") or "Untitled notice").strip()[:300],
        "sender": (data.get("sender") or "").strip()[:300],
        "source": (data.get("source") or "paste").strip()[:40],
        "category": (data.get("category") or "General").strip()[:60],
        "urgency": (data.get("urgency") or "normal").strip()[:20],
        "tldr": data.get("tldr") or "",
        "action_items": _dumps(data.get("action_items") or []),
        "deadlines": _dumps(data.get("deadlines") or []),
        "tags": _dumps(data.get("tags") or []),
        "body": (data.get("body") or "")[:20000],
        "mode": (data.get("mode") or "heuristic")[:20],
        "created_at": utcnow(),
    }
    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO summaries (
                id, subject, sender, source, category, urgency, tldr,
                action_items, deadlines, tags, body, mode, created_at
            ) VALUES (
                :id, :subject, :sender, :source, :category, :urgency, :tldr,
                :action_items, :deadlines, :tags, :body, :mode, :created_at
            )
            """,
            record,
        )
    return get_summary(record["id"]) or record


def get_summary(summary_id: str) -> dict | None:
    init_db()
    with get_connection() as connection:
        row = connection.execute(
            "SELECT * FROM summaries WHERE id = ?", (summary_id,)
        ).fetchone()
    return _summary_row(dict(row)) if row else None


def list_summaries(limit: int = 50, query: str = "") -> list[dict]:
    init_db()
    limit = max(1, min(int(limit or 50), 200))
    sql = "SELECT * FROM summaries"
    params: list = []
    if query:
        sql += " WHERE subject LIKE ? OR tldr LIKE ? OR body LIKE ?"
        needle = f"%{query}%"
        params = [needle, needle, needle]
    sql += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)
    with get_connection() as connection:
        rows = connection.execute(sql, params).fetchall()
    return [_summary_row(dict(row)) for row in rows]


def delete_summary(summary_id: str) -> bool:
    init_db()
    with get_connection() as connection:
        cursor = connection.execute(
            "DELETE FROM summaries WHERE id = ?", (summary_id,)
        )
    return bool(cursor.rowcount)


# ---------------------------------------------------------------------------
# Tasks
# ---------------------------------------------------------------------------

TASK_PRIORITIES = {"low", "medium", "high", "urgent"}
TASK_STATUSES = {"todo", "doing", "done"}


def _task_row(row: dict) -> dict:
    item = dict(row)
    item["tags"] = _json(item.get("tags"), [])
    item["overdue"] = bool(
        item.get("due_date")
        and item.get("status") != "done"
        and item["due_date"] < today().isoformat()
    )
    return item


def create_task(data: dict) -> dict:
    init_db()
    now = utcnow()
    priority = (data.get("priority") or "medium").lower()
    status = (data.get("status") or "todo").lower()
    record = {
        "id": new_id("task_"),
        "title": (data.get("title") or "Untitled task").strip()[:300],
        "notes": (data.get("notes") or "").strip()[:4000],
        "due_date": (data.get("due_date") or "").strip()[:32],
        "priority": priority if priority in TASK_PRIORITIES else "medium",
        "status": status if status in TASK_STATUSES else "todo",
        "tags": _dumps(data.get("tags") or []),
        "source_type": (data.get("source_type") or "manual")[:40],
        "source_id": (data.get("source_id") or "")[:80],
        "created_at": now,
        "updated_at": now,
        "completed_at": now if status == "done" else "",
    }
    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO tasks (
                id, title, notes, due_date, priority, status, tags,
                source_type, source_id, created_at, updated_at, completed_at
            ) VALUES (
                :id, :title, :notes, :due_date, :priority, :status, :tags,
                :source_type, :source_id, :created_at, :updated_at, :completed_at
            )
            """,
            record,
        )
    return get_task(record["id"]) or record


def get_task(task_id: str) -> dict | None:
    init_db()
    with get_connection() as connection:
        row = connection.execute(
            "SELECT * FROM tasks WHERE id = ?", (task_id,)
        ).fetchone()
    return _task_row(dict(row)) if row else None


def list_tasks(status: str = "", priority: str = "", query: str = "") -> list[dict]:
    init_db()
    clauses = []
    params: list = []
    if status and status in TASK_STATUSES:
        clauses.append("status = ?")
        params.append(status)
    if priority and priority in TASK_PRIORITIES:
        clauses.append("priority = ?")
        params.append(priority)
    if query:
        clauses.append("(title LIKE ? OR notes LIKE ?)")
        params.extend([f"%{query}%", f"%{query}%"])
    sql = "SELECT * FROM tasks"
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += (
        " ORDER BY CASE status WHEN 'done' THEN 2 WHEN 'doing' THEN 1 ELSE 0 END,"
        " CASE WHEN due_date = '' THEN 1 ELSE 0 END, due_date ASC,"
        " CASE priority WHEN 'urgent' THEN 0 WHEN 'high' THEN 1"
        " WHEN 'medium' THEN 2 ELSE 3 END, created_at DESC"
    )
    with get_connection() as connection:
        rows = connection.execute(sql, params).fetchall()
    return [_task_row(dict(row)) for row in rows]


def update_task(task_id: str, patch: dict) -> dict | None:
    init_db()
    existing = get_task(task_id)
    if not existing:
        return None
    updates: dict[str, str] = {}
    if "title" in patch and str(patch["title"]).strip():
        updates["title"] = str(patch["title"]).strip()[:300]
    if "notes" in patch:
        updates["notes"] = str(patch["notes"] or "")[:4000]
    if "due_date" in patch:
        updates["due_date"] = str(patch["due_date"] or "")[:32]
    if "priority" in patch:
        priority = str(patch["priority"]).lower()
        if priority in TASK_PRIORITIES:
            updates["priority"] = priority
    if "status" in patch:
        status = str(patch["status"]).lower()
        if status in TASK_STATUSES:
            updates["status"] = status
            updates["completed_at"] = utcnow() if status == "done" else ""
    if "tags" in patch:
        updates["tags"] = _dumps(patch["tags"] or [])
    if not updates:
        return existing
    updates["updated_at"] = utcnow()
    assignments = ", ".join(f"{key} = :{key}" for key in updates)
    updates["id"] = task_id
    with get_connection() as connection:
        connection.execute(
            f"UPDATE tasks SET {assignments} WHERE id = :id", updates
        )
    return get_task(task_id)


def delete_task(task_id: str) -> bool:
    init_db()
    with get_connection() as connection:
        cursor = connection.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    return bool(cursor.rowcount)


# ---------------------------------------------------------------------------
# Academic vault
# ---------------------------------------------------------------------------

def _vault_row(row: dict) -> dict:
    item = dict(row)
    item["tags"] = _json(item.get("tags"), [])
    item["starred"] = bool(item.get("starred"))
    return item


def create_resource(data: dict) -> dict:
    init_db()
    now = utcnow()
    record = {
        "id": new_id("res_"),
        "title": (data.get("title") or "Untitled resource").strip()[:300],
        "subject": (data.get("subject") or "General").strip()[:80],
        "branch": (data.get("branch") or "All").strip()[:80],
        "type": (data.get("type") or "link").strip()[:32],
        "url": (data.get("url") or "").strip()[:1200],
        "description": (data.get("description") or "").strip()[:2000],
        "tags": _dumps(data.get("tags") or []),
        "starred": 1 if data.get("starred") else 0,
        "created_at": now,
        "updated_at": now,
    }
    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO vault (
                id, title, subject, branch, type, url, description,
                tags, starred, created_at, updated_at
            ) VALUES (
                :id, :title, :subject, :branch, :type, :url, :description,
                :tags, :starred, :created_at, :updated_at
            )
            """,
            record,
        )
    return get_resource(record["id"]) or record


def get_resource(resource_id: str) -> dict | None:
    init_db()
    with get_connection() as connection:
        row = connection.execute(
            "SELECT * FROM vault WHERE id = ?", (resource_id,)
        ).fetchone()
    return _vault_row(dict(row)) if row else None


def list_resources(
    subject: str = "", branch: str = "", type_filter: str = "", query: str = ""
) -> list[dict]:
    init_db()
    clauses = []
    params: list = []
    if subject:
        clauses.append("subject = ?")
        params.append(subject)
    if branch and branch != "All":
        clauses.append("(branch = ? OR branch = 'All')")
        params.append(branch)
    if type_filter:
        clauses.append("type = ?")
        params.append(type_filter)
    if query:
        needle = f"%{query}%"
        clauses.append(
            "(title LIKE ? OR description LIKE ? OR subject LIKE ? OR tags LIKE ?)"
        )
        params.extend([needle, needle, needle, needle])
    sql = "SELECT * FROM vault"
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY starred DESC, updated_at DESC"
    with get_connection() as connection:
        rows = connection.execute(sql, params).fetchall()
    return [_vault_row(dict(row)) for row in rows]


def update_resource(resource_id: str, patch: dict) -> dict | None:
    init_db()
    existing = get_resource(resource_id)
    if not existing:
        return None
    updates: dict[str, str | int] = {}
    for field, limit in (
        ("title", 300),
        ("subject", 80),
        ("branch", 80),
        ("type", 32),
        ("url", 1200),
        ("description", 2000),
    ):
        if field in patch:
            updates[field] = str(patch.get(field) or "")[:limit]
    if "tags" in patch:
        updates["tags"] = _dumps(patch.get("tags") or [])
    if "starred" in patch:
        updates["starred"] = 1 if patch.get("starred") else 0
    if not updates:
        return existing
    updates["updated_at"] = utcnow()
    assignments = ", ".join(f"{key} = :{key}" for key in updates)
    updates["id"] = resource_id
    with get_connection() as connection:
        connection.execute(
            f"UPDATE vault SET {assignments} WHERE id = :id", updates
        )
    return get_resource(resource_id)


def delete_resource(resource_id: str) -> bool:
    init_db()
    with get_connection() as connection:
        cursor = connection.execute("DELETE FROM vault WHERE id = ?", (resource_id,))
    return bool(cursor.rowcount)


# ---------------------------------------------------------------------------
# Bookmarks
# ---------------------------------------------------------------------------

def _bookmark_row(row: dict) -> dict:
    item = dict(row)
    item["payload"] = _json(item.get("payload"), {})
    return item


def toggle_bookmark(data: dict) -> dict:
    """Create a bookmark, or remove it when the same item is already saved."""
    init_db()
    item_key = str(data.get("item_key") or "").strip()[:400]
    if not item_key:
        raise ValueError("item_key is required")
    existing = get_bookmark_by_key(item_key)
    if existing:
        delete_bookmark(existing["id"])
        return {"saved": False, "bookmark": None}
    record = {
        "id": new_id("bm_"),
        "item_key": item_key,
        "type": (data.get("type") or "item")[:40],
        "title": (data.get("title") or "")[:300],
        "subtitle": (data.get("subtitle") or "")[:300],
        "url": (data.get("url") or "")[:1200],
        "payload": _dumps(data.get("payload") or {}),
        "created_at": utcnow(),
    }
    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO bookmarks (id, item_key, type, title, subtitle, url, payload, created_at)
            VALUES (:id, :item_key, :type, :title, :subtitle, :url, :payload, :created_at)
            """,
            record,
        )
    return {"saved": True, "bookmark": get_bookmark(record["id"])}


def get_bookmark(bookmark_id: str) -> dict | None:
    init_db()
    with get_connection() as connection:
        row = connection.execute(
            "SELECT * FROM bookmarks WHERE id = ?", (bookmark_id,)
        ).fetchone()
    return _bookmark_row(dict(row)) if row else None


def get_bookmark_by_key(item_key: str) -> dict | None:
    init_db()
    with get_connection() as connection:
        row = connection.execute(
            "SELECT * FROM bookmarks WHERE item_key = ?", (item_key,)
        ).fetchone()
    return _bookmark_row(dict(row)) if row else None


def list_bookmarks(type_filter: str = "", query: str = "") -> list[dict]:
    init_db()
    clauses = []
    params: list = []
    if type_filter:
        clauses.append("type = ?")
        params.append(type_filter)
    if query:
        needle = f"%{query}%"
        clauses.append("(title LIKE ? OR subtitle LIKE ?)")
        params.extend([needle, needle])
    sql = "SELECT * FROM bookmarks"
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY created_at DESC"
    with get_connection() as connection:
        rows = connection.execute(sql, params).fetchall()
    return [_bookmark_row(dict(row)) for row in rows]


def delete_bookmark(bookmark_id: str) -> bool:
    init_db()
    with get_connection() as connection:
        cursor = connection.execute(
            "DELETE FROM bookmarks WHERE id = ?", (bookmark_id,)
        )
    return bool(cursor.rowcount)


# ---------------------------------------------------------------------------
# Opportunities
# ---------------------------------------------------------------------------

def _opportunity_row(row: dict) -> dict:
    item = dict(row)
    item["tags"] = _json(item.get("tags"), [])
    item["deadline_passed"] = bool(
        item.get("deadline") and item["deadline"] < today().isoformat()
    )
    return item


def upsert_opportunity(data: dict) -> dict:
    init_db()
    record = {
        "id": data.get("id") or new_id("opp_"),
        "title": (data.get("title") or "")[:300],
        "organizer": (data.get("organizer") or "")[:200],
        "description": (data.get("description") or "")[:2000],
        "why": (data.get("why") or "")[:1200],
        "track": (data.get("track") or "Hackathon")[:60],
        "mode": (data.get("mode") or "Online")[:40],
        "location": (data.get("location") or "")[:200],
        "deadline": (data.get("deadline") or "")[:32],
        "starts_at": (data.get("starts_at") or "")[:32],
        "prize": (data.get("prize") or "")[:200],
        "perks": (data.get("perks") or "")[:400],
        "url": (data.get("url") or "")[:1200],
        "tags": _dumps(data.get("tags") or []),
        "recurrence_days": int(data.get("recurrence_days") or 365),
        "source": (data.get("source") or "curated")[:40],
        "created_at": utcnow(),
    }
    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO opportunities (
                id, title, organizer, description, why, track, mode, location,
                deadline, starts_at, prize, perks, url, tags, recurrence_days,
                source, created_at
            ) VALUES (
                :id, :title, :organizer, :description, :why, :track, :mode, :location,
                :deadline, :starts_at, :prize, :perks, :url, :tags, :recurrence_days,
                :source, :created_at
            )
            ON CONFLICT(id) DO UPDATE SET
                title = excluded.title,
                organizer = excluded.organizer,
                description = excluded.description,
                why = excluded.why,
                track = excluded.track,
                mode = excluded.mode,
                location = excluded.location,
                deadline = excluded.deadline,
                starts_at = excluded.starts_at,
                prize = excluded.prize,
                perks = excluded.perks,
                url = excluded.url,
                tags = excluded.tags,
                recurrence_days = excluded.recurrence_days,
                source = excluded.source
            """,
            record,
        )
    return get_opportunity(record["id"]) or record


def get_opportunity(opportunity_id: str) -> dict | None:
    init_db()
    with get_connection() as connection:
        row = connection.execute(
            "SELECT * FROM opportunities WHERE id = ?", (opportunity_id,)
        ).fetchone()
    return _opportunity_row(dict(row)) if row else None


def list_opportunities(
    track: str = "",
    mode: str = "",
    deadline_window: str = "",
    query: str = "",
) -> list[dict]:
    init_db()
    clauses = ["1 = 1"]
    params: list = []
    if track and track != "All":
        clauses.append("track = ?")
        params.append(track)
    if mode and mode != "All":
        clauses.append("mode = ?")
        params.append(mode)
    if query:
        needle = f"%{query}%"
        clauses.append(
            "(title LIKE ? OR organizer LIKE ? OR description LIKE ? OR tags LIKE ?)"
        )
        params.extend([needle, needle, needle, needle])
    if deadline_window == "7":
        clauses.append("deadline != '' AND deadline <= ?")
        params.append((today() + timedelta(days=7)).isoformat())
    elif deadline_window == "30":
        clauses.append("deadline != '' AND deadline <= ?")
        params.append((today() + timedelta(days=30)).isoformat())
    elif deadline_window == "open":
        clauses.append("(deadline = '' OR deadline >= ?)")
        params.append(today().isoformat())
    sql = (
        "SELECT * FROM opportunities WHERE "
        + " AND ".join(clauses)
        + " ORDER BY CASE WHEN deadline = '' THEN 1 ELSE 0 END,"
        " deadline ASC, title ASC"
    )
    with get_connection() as connection:
        rows = connection.execute(sql, params).fetchall()
    return [_opportunity_row(dict(row)) for row in rows]


def count_opportunities() -> int:
    init_db()
    with get_connection() as connection:
        row = connection.execute("SELECT COUNT(*) AS total FROM opportunities").fetchone()
    return int(row["total"] if row else 0)


# ---------------------------------------------------------------------------
# Aggregates
# ---------------------------------------------------------------------------

def get_stats() -> dict:
    init_db()
    today_iso = today().isoformat()
    week_ahead = (today() + timedelta(days=7)).isoformat()
    with get_connection() as connection:
        tasks_open = connection.execute(
            "SELECT COUNT(*) AS total FROM tasks WHERE status != 'done'"
        ).fetchone()["total"]
        tasks_done = connection.execute(
            "SELECT COUNT(*) AS total FROM tasks WHERE status = 'done'"
        ).fetchone()["total"]
        due_week = connection.execute(
            "SELECT COUNT(*) AS total FROM tasks WHERE status != 'done'"
            " AND due_date != '' AND due_date <= ?",
            (week_ahead,),
        ).fetchone()["total"]
        overdue = connection.execute(
            "SELECT COUNT(*) AS total FROM tasks WHERE status != 'done'"
            " AND due_date != '' AND due_date < ?",
            (today_iso,),
        ).fetchone()["total"]
        summaries = connection.execute(
            "SELECT COUNT(*) AS total FROM summaries"
        ).fetchone()["total"]
        bookmarks = connection.execute(
            "SELECT COUNT(*) AS total FROM bookmarks"
        ).fetchone()["total"]
        vault = connection.execute("SELECT COUNT(*) AS total FROM vault").fetchone()[
            "total"
        ]
        starred = connection.execute(
            "SELECT COUNT(*) AS total FROM vault WHERE starred = 1"
        ).fetchone()["total"]
    return {
        "tasks_open": tasks_open,
        "tasks_done": tasks_done,
        "due_week": due_week,
        "overdue": overdue,
        "summaries": summaries,
        "bookmarks": bookmarks,
        "vault": vault,
        "starred": starred,
        "opportunities": count_opportunities(),
        "streak": min(7, tasks_done) or 1,
    }


def search_all(query: str, limit: int = 8) -> dict:
    """Lightweight cross-module search used by the command palette."""
    query = (query or "").strip()
    if not query:
        return {"tasks": [], "summaries": [], "vault": [], "opportunities": [], "bookmarks": []}
    return {
        "tasks": list_tasks(query=query)[:limit],
        "summaries": list_summaries(limit=limit, query=query),
        "vault": list_resources(query=query)[:limit],
        "opportunities": list_opportunities(query=query)[:limit],
        "bookmarks": list_bookmarks(query=query)[:limit],
    }
