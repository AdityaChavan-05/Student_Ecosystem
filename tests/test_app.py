"""End-to-end API tests for Student Ecosystem.

The suite runs against a throwaway SQLite database so it never touches the
developer's real data. External network calls are tolerated: every fetcher has
a deterministic fallback, which is exactly what these tests assert.
"""

from __future__ import annotations

import io
import json
import os
import tempfile
from pathlib import Path

import pytest

# Configure an isolated database *before* importing the application.
_TMP_DIR = Path(tempfile.mkdtemp(prefix="student-ecosystem-tests-"))
os.environ["DATABASE_PATH"] = str(_TMP_DIR / "test.db")
os.environ["AI_API_KEY"] = ""
os.environ["GEMINI_API_KEY"] = ""

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
    assert data["ai"] in {"fallback", "configured"}
    assert "model" not in data


def test_bootstrap(client):
    response = client.get("/api/bootstrap")
    assert response.status_code == 200
    data = response.get_json()
    assert data["profile"]["name"]
    assert "Computer Science" in data["branches"]
    assert set(data["features"]) >= {"ai", "social"}
    assert "model" not in data["features"]
    assert "ai_mode" not in data["features"]
    assert "linkedin" in data["features"]["social"]
    assert isinstance(data["features"]["social"]["links"], list)
    assert data["topics"]["Computer Science"]
    assert "tasks_open" in data["stats"]


def test_settings_keep_scalar_values_as_strings(client):
    application.update_settings({"name": "123"})
    assert application.get_settings()["name"] == "123"
    application.update_settings({"name": "MIT-WPU Student"})


def test_gmail_oauth_requires_stable_secret(client, monkeypatch):
    monkeypatch.setattr(application.Config, "SECRET_KEY_CONFIGURED", False)
    status = client.get("/api/gmail/status").get_json()
    assert status["connected"] is False
    assert status["configured"] is False
    assert client.get("/auth/google").status_code == 503


def test_vercel_builds_include_static_assets():
    import json

    vercel = json.loads(
        (Path(__file__).resolve().parents[1] / "vercel.json").read_text(encoding="utf-8")
    )
    assert any(
        build.get("src") == "static/**" and build.get("use") == "@vercel/static"
        for build in vercel["builds"]
    )


def test_ui_hides_provider_and_raw_api_payloads():
    root = Path(__file__).resolve().parents[1]
    template = (root / "templates" / "index.html").read_text(encoding="utf-8")
    scripts = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted((root / "static" / "js").glob("*.js"))
    )

    # Raw diagnostic payloads must not be linked from the settings screen.
    assert "/api/bootstrap" not in template
    assert "/api/health" not in template

    # No provider, model or feed-source details may be rendered in the UI.
    for needle in (
        "Gemini",
        "gemini-",
        "Summarized with",
        "Live RSS briefing",
        "Written by Gemini",
        "Open official source",
        "Read original",
        "MIT-WPU official",
        "state.features.model",
        "state.features.ai_mode",
        "item.source",
        "summary.sender",
        "message.sender",
    ):
        assert needle not in scripts, needle

    # New-post alerts use a neutral label and a dedicated campus card.
    assert "stats.social_alerts" in scripts
    assert "Latest post" in scripts
    assert "New campus posts will appear here" in scripts
    assert 'id="campus-latest"' in template


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


def test_news_query_filters_cached_feed(client):
    data = client.get("/api/news?branch=Computer%20Science&limit=3&q=no-such-engineering-topic-xyz").get_json()
    assert data["query"] == "no-such-engineering-topic-xyz"
    assert data["articles"] == []
    assert data["count"] == 0


def test_social_updates_are_honest_without_credentials(client, monkeypatch):
    monkeypatch.setattr(
        application.Config,
        "SOCIAL_LINKS_JSON",
        '[{"label":"MIT-WPU LinkedIn","url":"https://www.linkedin.com/school/mitwpu/","platform":"linkedin"}]',
    )
    monkeypatch.setattr(application.Config, "LINKEDIN_ACCESS_TOKEN", "")
    monkeypatch.setattr(application.Config, "LINKEDIN_AUTHOR_URNS", ())
    monkeypatch.setattr(application.Config, "INSTAGRAM_ACCESS_TOKEN", "")
    monkeypatch.setattr(application.Config, "INSTAGRAM_USER_ID", "")

    data = client.get("/api/social-updates?limit=7").get_json()
    assert data["count"] == 0
    assert data["updates"] == []
    assert data["profiles"][0]["label"] == "MIT-WPU LinkedIn"
    assert data["status"]["linkedin"] is False
    assert "officially authorised" in data["note"]


def test_linkedin_adapter_uses_official_posts_api(monkeypatch):
    import social_fetcher

    calls = []

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "elements": [
                    {
                        "id": "urn:li:share:12345",
                        "commentary": "Placement talk by {mention|urn:li:organization:99|MIT-WPU} today.",
                        "publishedAt": 1700000000000,
                    }
                ]
            }

    def fake_get(url, params, headers, timeout):
        calls.append((url, params, headers, timeout))
        return Response()

    monkeypatch.setattr(application.Config, "LINKEDIN_ACCESS_TOKEN", "dummy-token")
    monkeypatch.setattr(
        application.Config, "LINKEDIN_AUTHOR_URNS", ("urn:li:organization:99",)
    )
    monkeypatch.setattr(social_fetcher.SESSION, "get", fake_get)

    updates = social_fetcher.fetch_linkedin_updates(limit=5)

    assert len(updates) == 1
    assert calls[0][0] == "https://api.linkedin.com/rest/posts"
    assert calls[0][1]["q"] == "author"
    assert calls[0][1]["author"] == "urn:li:organization:99"
    assert calls[0][2]["X-RestLi-Method"] == "FINDER"
    assert "MIT-WPU" in updates[0]["title"]
    assert updates[0]["published_at"] == "2023-11-14T22:13:20+00:00"
    assert updates[0]["link"] == "https://www.linkedin.com/feed/update/urn:li:share:12345/"


def test_instagram_discovery_skipped_without_facebook_host(monkeypatch):
    import social_fetcher

    calls = []

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"data": []}

    def fake_get(url, params, timeout):
        calls.append((url, params))
        return Response()

    monkeypatch.setattr(application.Config, "INSTAGRAM_ACCESS_TOKEN", "dummy-token")
    monkeypatch.setattr(application.Config, "INSTAGRAM_USER_ID", "123")
    monkeypatch.setattr(application.Config, "INSTAGRAM_API_HOST", "graph.instagram.com")
    monkeypatch.setattr(application.Config, "INSTAGRAM_DISCOVERY_USERNAMES", ("mitwpu",))
    monkeypatch.setattr(social_fetcher.SESSION, "get", fake_get)

    assert social_fetcher.fetch_instagram_updates(limit=5) == []
    assert len(calls) == 1
    assert "business_discovery" not in calls[0][1]["fields"]


def test_instagram_watch_uses_official_business_discovery(monkeypatch):
    import social_fetcher

    calls = []

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "business_discovery": {
                    "media": {
                        "data": [
                            {
                                "id": "watch-2",
                                "caption": "Second campus post",
                                "timestamp": "2026-11-28T12:00:00+00:00",
                                "permalink": "https://www.instagram.com/p/second/",
                            },
                            {
                                "id": "watch-1",
                                "caption": "First campus post",
                                "timestamp": "2026-11-27T12:00:00+00:00",
                                "permalink": "https://www.instagram.com/p/first/",
                            },
                        ]
                    }
                }
            }

    def fake_get(url, params, timeout):
        calls.append((url, params))
        return Response()

    monkeypatch.setattr(application.Config, "INSTAGRAM_ACCESS_TOKEN", "dummy-token")
    monkeypatch.setattr(application.Config, "INSTAGRAM_USER_ID", "123")
    monkeypatch.setattr(application.Config, "INSTAGRAM_API_HOST", "graph.facebook.com")
    monkeypatch.setattr(
        application.Config, "INSTAGRAM_DISCOVERY_USERNAMES", ("mitwpuofficial",)
    )
    monkeypatch.setattr(application.Config, "INSTAGRAM_WATCH_LIMIT", 2)
    monkeypatch.setattr(social_fetcher.SESSION, "get", fake_get)

    updates = social_fetcher.fetch_instagram_watch_updates(limit=2)

    assert len(updates) == 2
    assert updates[0]["title"] == "Second campus post"
    assert updates[0]["watch"] is True
    assert calls[0][0] == "https://graph.facebook.com/v26.0/123"
    fields = calls[0][1]["fields"]
    assert "business_discovery.username(mitwpuofficial)" in fields
    assert "media.limit(2)" in fields
    assert "stories" not in fields.lower()


def test_social_poll_is_protected_and_alerts_only_on_new_posts(client, monkeypatch):
    import database
    import social_fetcher

    secret = "test-cron-secret"
    post_id = ["poll-existing"]

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "business_discovery": {
                    "media": {
                        "data": [
                            {
                                "id": post_id[0],
                                "caption": "A real campus post",
                                "timestamp": "2026-11-28T09:00:00+00:00",
                                "permalink": "https://www.instagram.com/p/real-post/",
                            }
                        ]
                    }
                }
            }

    def fake_get(url, params, timeout):
        return Response()

    with database.get_connection() as connection:
        connection.execute("DELETE FROM social_posts")

    monkeypatch.setattr(application.Config, "CRON_SECRET", secret)
    monkeypatch.setattr(application.Config, "INSTAGRAM_ACCESS_TOKEN", "dummy-token")
    monkeypatch.setattr(application.Config, "INSTAGRAM_USER_ID", "123")
    monkeypatch.setattr(application.Config, "INSTAGRAM_API_HOST", "graph.facebook.com")
    monkeypatch.setattr(
        application.Config, "INSTAGRAM_DISCOVERY_USERNAMES", ("mitwpuofficial",)
    )
    monkeypatch.setattr(social_fetcher.SESSION, "get", fake_get)

    headers = {"Authorization": f"Bearer {secret}"}
    try:
        assert client.get("/api/social/poll").status_code == 401

        baseline = client.get("/api/social/poll", headers=headers).get_json()
        assert baseline["status"] == "ok"
        assert baseline["checked"] == 1
        assert baseline["new_alerts"] == 0
        assert baseline["stats"]["social_alerts"] == 0

        post_id[0] = "poll-new"
        polled = client.get("/api/social/poll", headers=headers).get_json()
        assert polled["new_alerts"] == 1
        assert polled["stats"]["social_alerts"] == 1

        notifications = client.get("/api/notifications").get_json()
        social_items = [item for item in notifications["items"] if item["type"] == "social"]
        assert len(social_items) == 1
        assert social_items[0]["title"] == "A real campus post"
        assert notifications["stats"]["social_alerts"] == 1

        marked = client.post("/api/social-alerts/read", json={}).get_json()
        assert marked["marked"] == 1
        assert marked["stats"]["social_alerts"] == 0
        assert client.get("/api/social/poll", headers=headers).get_json()["new_alerts"] == 0
    finally:
        with database.get_connection() as connection:
            connection.execute("DELETE FROM social_posts")


def test_branch_change_drops_stale_preferences(client):
    client.patch("/api/profile", json={"news_preferences": []})
    response = client.patch(
        "/api/profile",
        json={
            "branch": "Electronics",
            "news_preferences": [
                "Computer Science",
                "Electronics",
                "Artificial Intelligence",
            ],
        },
    )
    assert response.status_code == 200
    assert response.get_json()["profile"]["news_preferences"] == ["Artificial Intelligence"]
    client.patch("/api/profile", json={"branch": "Computer Science", "news_preferences": []})


def test_profile_news_preferences_and_topics(client):
    response = client.patch(
        "/api/profile",
        json={"news_preferences": ["Artificial Intelligence", "Robotics", "Artificial Intelligence"]},
    )
    assert response.status_code == 200
    assert response.get_json()["profile"]["news_preferences"] == ["Artificial Intelligence"]

    bootstrap = client.get("/api/bootstrap").get_json()
    assert "artificial intelligence" in bootstrap["topics"]["Artificial Intelligence"]
    client.patch("/api/profile", json={"news_preferences": []})


def test_briefing_and_refresh(client):
    data = client.get("/api/briefing").get_json()
    assert data["briefing"]["summary"]
    assert isinstance(data["briefing"]["priorities"], list)

    refreshed = client.get("/api/briefing?refresh=true").get_json()
    assert refreshed["briefing"]["summary"]


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


def test_spa_restores_mail_summarizer_controls(client):
    html = client.get("/").get_data(as_text=True)
    for element_id in (
        "mail-form", "mail-body", "mail-file", "mail-submit", "mail-result",
        "mail-history", "news-topics", "campus-shortcuts", "gmail-auto",
    ):
        assert f'id="{element_id}"' in html, element_id
    assert "display: none !important" not in html.split("id=\"view-mail\"")[1].split("<!-- ============ END MAIL")[0]


def test_unknown_api_returns_json_404(client):
    response = client.get("/api/does-not-exist")
    assert response.status_code == 404
    assert "error" in response.get_json()


# ---------------------------------------------------------------------------
# Prompt rendering and AI response handling (no real API key or network)
# ---------------------------------------------------------------------------


def test_notice_prompt_preserves_json_braces(monkeypatch):
    import ai_summarizer

    captured = {}

    def fake_generate(prompt, json_mode=True):
        captured["prompt"] = prompt
        return json.dumps(
            {
                "tldr": "The portal timetable was published.",
                "category": "Examination",
                "urgency": "high",
                "action_items": ["Verify your subjects on the portal."],
                "deadlines": [{"label": "Report changes", "date": "2026-11-28"}],
                "tags": ["exam"],
            }
        )

    monkeypatch.setattr(ai_summarizer, "ai_available", lambda: True)
    monkeypatch.setattr(ai_summarizer, "_generate", fake_generate)

    result = ai_summarizer.summarize_notice(
        "The examination timetable for the unique prompt test was published today.",
        subject="Prompt regression notice",
        sender="examination@mitwpu.edu.in",
    )

    assert result["mode"] == "ai"
    assert '"tldr"' in captured["prompt"]
    assert '"action_items"' in captured["prompt"]
    assert "SUBJECT: Prompt regression notice" in captured["prompt"]
    assert "TODAY = " in captured["prompt"]


def test_news_prompt_preserves_json_braces(monkeypatch):
    import ai_summarizer

    captured = {}

    def fake_generate(prompt, json_mode=True):
        captured["prompt"] = prompt
        return json.dumps(
            {
                "articles": [
                    {
                        "index": 0,
                        "tldr": "A new chip design was announced.",
                        "bullets": ["It may reduce power use.", "Details are in the paper."],
                        "tags": ["semiconductors"],
                    }
                ]
            }
        )

    monkeypatch.setattr(ai_summarizer, "ai_available", lambda: True)
    monkeypatch.setattr(ai_summarizer, "_generate", fake_generate)

    article = {
        "title": "Unique semiconductor prompt regression story",
        "link": "https://example.com/prompt-regression-news",
        "description": "Researchers described a lower-power chip architecture.",
    }
    result = ai_summarizer.summarize_news_batch([article])

    assert result[0]["mode"] == "ai"
    assert '"articles"' in captured["prompt"]
    assert '"index": 0' in captured["prompt"]
    assert "Unique semiconductor prompt regression story" in captured["prompt"]


def test_briefing_prompt_preserves_json_braces(monkeypatch):
    import ai_summarizer

    captured = {}

    def fake_generate(prompt, json_mode=True):
        captured["prompt"] = prompt
        return json.dumps(
            {
                "headline": "Student prompt regression check",
                "summary": "A short AI briefing summary.",
                "priorities": ["Finish the prompt regression task."],
            }
        )

    monkeypatch.setattr(ai_summarizer, "ai_available", lambda: True)
    monkeypatch.setattr(ai_summarizer, "_generate", fake_generate)

    result = ai_summarizer.generate_briefing(
        {
            "student": "Prompt Student",
            "branch": "Computer Science",
            "tasks": [{"title": "Finish the prompt regression task"}],
            "campus": [],
            "opportunities": [],
            "news": [],
        },
        force=True,
    )

    assert result["mode"] == "ai"
    assert '"headline"' in captured["prompt"]
    assert '"summary"' in captured["prompt"]
    assert '"priorities"' in captured["prompt"]
    assert "Prompt Student" in captured["prompt"]


def test_malformed_ai_responses_fall_back_without_crashing(monkeypatch):
    import ai_summarizer

    monkeypatch.setattr(ai_summarizer, "ai_available", lambda: True)
    monkeypatch.setattr(ai_summarizer, "_generate", lambda prompt, json_mode=True: "not json")

    notice = ai_summarizer.summarize_notice(
        "This is a unique malformed response notice with enough text for extraction.",
        subject="Malformed response test",
    )
    assert notice["mode"] == "heuristic"
    assert notice["tldr"]

    brief = ai_summarizer.generate_briefing(
        {"student": "Malformed Student", "branch": "Electronics", "tasks": []},
        force=True,
    )
    assert brief["mode"] == "heuristic"
    assert brief["summary"]


def test_empty_notice_input_is_handled():
    import ai_summarizer

    assert "Paste an email" in ai_summarizer.summarize_notice("   ")["tldr"]


def test_summarize_endpoint_survives_bad_ai_response(client, monkeypatch):
    import ai_summarizer

    monkeypatch.setattr(ai_summarizer, "ai_available", lambda: True)
    monkeypatch.setattr(ai_summarizer, "_generate", lambda prompt, json_mode=True: "not json")

    response = client.post(
        "/api/summarize",
        json={
            "text": "A unique route-level malformed response notice with enough text to summarize.",
            "subject": "Route malformed response test",
        },
    )
    assert response.status_code == 201
    data = response.get_json()
    assert data["ai_mode"] == "heuristic"
    assert data["summary"]["tldr"]
    client.delete(f"/api/summaries/{data['summary']['id']}")


# ---------------------------------------------------------------------------
# News throttling and shared cache
# ---------------------------------------------------------------------------


def test_rss_429_stops_after_bounded_retry(monkeypatch):
    import news_fetcher

    calls = []

    class ThrottledResponse:
        status_code = 429
        headers = {"Retry-After": "0"}
        content = b""

        def raise_for_status(self):
            return None

    def fake_get(url, timeout):
        calls.append(url)
        return ThrottledResponse()

    monkeypatch.setattr(news_fetcher.Config, "NEWS_FETCH_ATTEMPTS", 2)
    monkeypatch.setattr(news_fetcher, "_retry_delay", lambda response=None, attempt=1: 0.0)
    monkeypatch.setattr(news_fetcher.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(news_fetcher.SESSION, "get", fake_get)
    monkeypatch.setattr(news_fetcher, "fetch_publication_feeds", lambda per_feed=12: [])

    result = news_fetcher.fetch_news("Computer Science", limit=3)

    assert len(calls) == 4, "two feeds x one retry each; no aggressive loop"
    assert result["throttled"] is True
    assert result["source_status"]["google"] == "throttled"
    assert result["articles"], "a clearly-marked curated list is still returned"


def test_news_cache_is_shared_across_limits(monkeypatch):
    store = {}
    calls = []
    articles = [
        {
            "title": f"Shared cache article {index}",
            "link": f"https://example.com/shared-cache-{index}",
            "description": "A short article description with enough detail for the test.",
        }
        for index in range(4)
    ]

    def fake_get(key, **kwargs):
        return store.get(key)

    def fake_set(key, value, **kwargs):
        store[key] = value
        return True

    def fake_fetch(branch, limit):
        calls.append(limit)
        return {"articles": articles, "throttled": False, "source_status": {}}

    monkeypatch.setattr(application, "get_cached_value", fake_get)
    monkeypatch.setattr(application, "set_cached_value", fake_set)
    monkeypatch.setattr(application, "fetch_news", fake_fetch)
    monkeypatch.setattr(
        application,
        "summarize_news_batch",
        lambda items: [
            {"tldr": "Cached brief", "bullets": [], "tags": [], "mode": "heuristic"}
            for _ in items
        ],
    )

    first = application.load_news("Electrical", 2)
    second = application.load_news("Electrical", 5)

    assert len(calls) == 1
    assert len(first["articles"]) == 2
    assert len(second["articles"]) == 4
    assert second["cached"] is True


def test_cached_query_search_uses_full_feed(monkeypatch):
    cached = {
        "branch": "Civil",
        "ai_mode": "heuristic",
        "articles": [
            {"title": "Bridge inspection rules", "description": "Structures", "tags": []},
            {"title": "Urban transit plan", "description": "Cities", "tags": []},
            {"title": "Concrete mix study", "description": "Materials", "tags": []},
        ],
    }
    key = application.cache_key("news-feed", "Civil")
    monkeypatch.setattr(
        application,
        "get_cached_value",
        lambda cache_key, **kwargs: cached if cache_key == key else None,
    )

    payload = application.load_news("Civil", 1, query="concrete")

    assert payload["count"] == 1
    assert payload["articles"][0]["title"] == "Concrete mix study"


def test_throttled_news_prefers_recent_cached_feed(monkeypatch):
    stale = {
        "branch": "Mechanical",
        "ai_mode": "heuristic",
        "updated_at": "2026-11-27T00:00:00+00:00",
        "articles": [
            {
                "title": "Last known good story",
                "link": "https://example.com/last-good",
                "description": "A cached article from before the provider throttled us.",
                "tldr": "Cached brief",
                "tags": [],
            }
        ],
        "source_status": {"google": "ok"},
    }

    def fake_get(key, **kwargs):
        if kwargs.get("allow_stale"):
            return stale
        return None

    def fake_fetch(branch, limit):
        return {
            "articles": [
                {"title": "Curated fallback", "fallback": True, "description": "Fallback"}
            ],
            "throttled": True,
            "source_status": {"google": "throttled"},
        }

    monkeypatch.setattr(application, "get_cached_value", fake_get)
    monkeypatch.setattr(application, "set_cached_value", lambda key, value, **kwargs: True)
    monkeypatch.setattr(application, "fetch_news", fake_fetch)

    payload = application.load_news("Mechanical", 3)

    assert payload["stale"] is True
    assert payload["articles"][0]["title"] == "Last known good story"
    assert "throttled" in payload["notice"]
