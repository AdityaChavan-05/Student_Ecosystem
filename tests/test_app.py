"""End-to-end API tests for Student Ecosystem.

The suite runs against a throwaway SQLite database so it never touches the
developer's real data. External network calls are tolerated: every fetcher has
a deterministic fallback, which is exactly what these tests assert.
"""

from __future__ import annotations

import io
import os
import tempfile
from pathlib import Path

import pytest

# Configure an isolated database *before* importing the application.
_TMP_DIR = Path(tempfile.mkdtemp(prefix="student-ecosystem-tests-"))
os.environ["DATABASE_PATH"] = str(_TMP_DIR / "test.db")
os.environ.pop("AI_API_KEY", None)
os.environ.pop("GEMINI_API_KEY", None)

import app as application  # noqa: E402  (must follow env setup)


@pytest.fixture(scope="module")
def client():
    application.app.config.update(TESTING=True)
    with application.app.test_client() as test_client:
        yield test_client


NOTICE = (
    "Dear students, the end-semester examination timetable has been published "
    "on the portal. Please verify your subjects and report discrepancies by "
    "28 November 2026. Hall tickets will be available three days before the "
    "first examination. Students with pending fee dues will not be issued a "
    "hall ticket. Carry your ID card and a printed hall ticket to every "
    "examination. Contact the examination cell for assistance."
)


# ---------------------------------------------------------------------------
# Core
# ---------------------------------------------------------------------------


def test_health(client):
    data = client.get("/api/health").get_json()
    assert data["status"] == "ok"
    assert data["database"] == "sqlite"
    assert data["ai"] in {"fallback", "live"}


def test_bootstrap(client):
    response = client.get("/api/bootstrap")
    assert response.status_code == 200
    data = response.get_json()
    assert data["profile"]["name"]
    assert "Computer Science" in data["branches"]
    assert set(data["features"]) >= {"ai", "ai_mode", "model"}
    assert "tasks_open" in data["stats"]


def test_profile_round_trip(client):
    response = client.patch(
        "/api/profile", json={"name": "Test Student", "branch": "Artificial Intelligence"}
    )
    assert response.status_code == 200
    assert response.get_json()["profile"]["name"] == "Test Student"
    client.patch("/api/profile", json={"name": "MIT-WPU Student", "branch": "Computer Science"})


# ---------------------------------------------------------------------------
# Feeds
# ---------------------------------------------------------------------------


def test_campus_feed_never_empty(client):
    data = client.get("/api/college-updates?limit=6").get_json()
    assert data["updates"], "campus feed must always return curated content"
    assert data["status"]["mode"] in {"live", "curated"}
    first = data["updates"][0]
    assert first["title"]
    assert "category" in first


def test_opportunities_and_filters(client):
    data = client.get("/api/opportunities").get_json()
    assert len(data["opportunities"]) >= 10
    assert data["tracks"]
    item = data["opportunities"][0]
    for key in ("title", "deadline", "mode", "prize", "why"):
        assert key in item

    filtered = client.get("/api/opportunities?mode=Online").get_json()
    assert all(entry["mode"] == "Online" for entry in filtered["opportunities"])


def test_news_briefings(client):
    data = client.get("/api/news?branch=Computer%20Science&limit=3").get_json()
    assert data["articles"]
    article = data["articles"][0]
    assert article["title"]
    assert article.get("tldr")


def test_briefing(client):
    data = client.get("/api/briefing").get_json()
    assert data["briefing"]["summary"]
    assert isinstance(data["briefing"]["priorities"], list)


def test_search_and_notifications(client):
    search = client.get("/api/search?q=exam").get_json()
    assert set(search) >= {"tasks", "opportunities", "vault"}
    notifications = client.get("/api/notifications").get_json()
    assert "items" in notifications


# ---------------------------------------------------------------------------
# Mail summarizer
# ---------------------------------------------------------------------------


def test_summarize_json_creates_summary_and_task(client):
    response = client.post(
        "/api/summarize",
        json={
            "text": NOTICE,
            "subject": "End-semester examination timetable",
            "sender": "examination@mitwpu.edu.in",
            "create_task": True,
        },
    )
    assert response.status_code == 201
    data = response.get_json()
    summary = data["summary"]
    assert summary["id"]
    assert summary["tldr"]
    assert summary["category"]
    assert summary["deadlines"], "the stated date must be extracted"
    deadline = summary["deadlines"][0]
    assert deadline["date"] == "2026-11-28"
    assert "…" not in deadline["label"] or len(deadline["label"]) <= 90
    assert not deadline["label"].startswith(("lease", "ease"))
    assert summary["action_items"]
    assert data["task"]["source_type"] == "summary"

    listed = client.get("/api/summaries").get_json()
    assert any(item["id"] == summary["id"] for item in listed["summaries"])

    converted = client.post(f"/api/summaries/{summary['id']}/task")
    assert converted.status_code == 201
    assert converted.get_json()["task"]["title"]

    assert client.delete(f"/api/summaries/{summary['id']}").status_code == 200


def test_summarize_txt_upload(client):
    response = client.post(
        "/api/summarize",
        data={
            "file": (io.BytesIO(NOTICE.encode("utf-8")), "notice.txt"),
            "subject": "Uploaded notice",
        },
        content_type="multipart/form-data",
    )
    assert response.status_code == 201
    summary = response.get_json()["summary"]
    assert summary["source"] in {"upload", "txt"}
    client.delete(f"/api/summaries/{summary['id']}")


def test_summarize_eml_upload(client):
    eml = (
        "From: dean@mitwpu.edu.in\n"
        "To: students@mitwpu.edu.in\n"
        "Subject: Robotics workshop\n"
        "Date: Mon, 10 Nov 2026 10:00:00 +0530\n"
        "\n"
        "A robotics workshop will be held on 25 November 2026 in the "
        "auditorium. Register by 20 November 2026 as seats are limited.\n"
    )
    response = client.post(
        "/api/summarize",
        data={"file": (io.BytesIO(eml.encode("utf-8")), "workshop.eml")},
        content_type="multipart/form-data",
    )
    assert response.status_code == 201
    summary = response.get_json()["summary"]
    assert summary["subject"] == "Robotics workshop"
    assert summary["deadlines"]
    client.delete(f"/api/summaries/{summary['id']}")


def test_summarize_rejects_empty_input(client):
    response = client.post("/api/summarize", json={"text": ""})
    assert response.status_code == 422
    assert "error" in response.get_json()


# ---------------------------------------------------------------------------
# Tasks
# ---------------------------------------------------------------------------


def test_task_crud_and_validation(client):
    created = client.post(
        "/api/tasks",
        json={
            "title": "Submit DBMS assignment",
            "due_date": "2026-11-22",
            "priority": "high",
            "tags": ["dbms", "exam"],
        },
    )
    assert created.status_code == 201
    task = created.get_json()["task"]
    assert task["status"] == "todo"

    updated = client.patch(f"/api/tasks/{task['id']}", json={"status": "done"})
    assert updated.status_code == 200
    assert updated.get_json()["task"]["status"] == "done"
    assert updated.get_json()["task"]["completed_at"]

    invalid = client.patch(f"/api/tasks/{task['id']}", json={"status": "nonsense"})
    assert invalid.status_code == 422

    missing = client.patch(f"/api/tasks/{task['id']}", json={"title": "   "})
    assert missing.status_code == 422

    assert client.delete(f"/api/tasks/{task['id']}").status_code == 200
    assert client.delete(f"/api/tasks/{task['id']}").status_code == 404


# ---------------------------------------------------------------------------
# Vault & bookmarks
# ---------------------------------------------------------------------------


def test_vault_crud(client):
    listed = client.get("/api/vault").get_json()
    assert len(listed["resources"]) >= 20

    created = client.post(
        "/api/vault",
        json={
            "title": "Test resource",
            "subject": "Testing",
            "type": "link",
            "url": "https://example.com",
        },
    )
    assert created.status_code == 201
    resource = created.get_json()["resource"]

    patched = client.patch(f"/api/vault/{resource['id']}", json={"starred": True})
    assert patched.status_code == 200
    assert patched.get_json()["resource"]["starred"] is True

    assert client.delete(f"/api/vault/{resource['id']}").status_code == 200


def test_bookmark_toggle(client):
    payload = {
        "item_key": "opportunity:test-sih",
        "type": "opportunity",
        "title": "Smart India Hackathon",
        "subtitle": "Hackathon",
        "url": "https://sih.gov.in",
    }
    saved = client.post("/api/bookmarks", json=payload).get_json()
    assert saved["saved"] is True

    listed = client.get("/api/bookmarks").get_json()
    assert any(item["item_key"] == "opportunity:test-sih" for item in listed["bookmarks"])

    removed = client.post("/api/bookmarks", json=payload).get_json()
    assert removed["saved"] is False
    assert client.delete("/api/bookmarks/does-not-exist").status_code == 404


# ---------------------------------------------------------------------------
# Assets & SPA routing
# ---------------------------------------------------------------------------


def test_spa_and_assets(client):
    index = client.get("/")
    assert index.status_code == 200
    html = index.get_data(as_text=True)
    for asset in ("/static/css/app.css", "/static/js/core.js", "/static/js/app.js"):
        assert asset in html

    for path in (
        "/static/css/app.css",
        "/static/js/core.js",
        "/static/js/views.js",
        "/static/js/tools.js",
        "/static/js/app.js",
        "/static/favicon.svg",
        "/manifest.webmanifest",
    ):
        assert client.get(path).status_code == 200, path

    for legacy in ("/news", "/college", "/opportunities", "/mail", "/vault", "/tasks"):
        response = client.get(legacy)
        assert response.status_code in {301, 302}, legacy


def test_unknown_api_returns_json_404(client):
    response = client.get("/api/does-not-exist")
    assert response.status_code == 404
    assert "error" in response.get_json()
