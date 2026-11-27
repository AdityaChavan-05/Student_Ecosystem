# AI_HANDOFF.md — Student Ecosystem

## 1. Project name and purpose

**Student Ecosystem** is a Flask + SQLite + vanilla-JavaScript single-page dashboard for MIT-WPU engineering students. It provides campus updates, opportunities, AI/news briefings, notices/email summarization, an academic vault, task hub, saved library and settings. The goal of this session was to debug and stabilize production errors while preserving the existing frontend and architecture.

## 2. Project architecture

- **Backend:** Flask app (`app.py`) exposing JSON APIs and serving the SPA.
- **Persistence:** SQLite (`database.py`), with a small `app_cache` table used for feed/AI/campus/social caching.
- **AI:** `ai_summarizer.py` uses Gemini when `AI_API_KEY` is configured and deterministic local extractive fallbacks otherwise.
- **Feeds:** `news_fetcher.py` (Google News, Bing News, publication RSS), `college_fetcher.py`, `social_fetcher.py`.
- **Frontend:** static HTML/CSS/JS in `templates/index.html`, `static/js/*.js`, `static/css/app.css`.
- **Deployment:** Vercel via `vercel.json` (`@vercel/static` for `static/**`, `@vercel/python` for `app.py`).

## 3. Relevant directory structure

```text
Student_Ecosystem/
  app.py                 # Flask routes, feed loading, briefing context
  ai_summarizer.py       # NOTICE_PROMPT, NEWS_PROMPT, BRIEFING_PROMPT, fallbacks
  news_fetcher.py        # RSS fetch, retry logic, fetch_news(), get_news()
  config.py              # environment-driven settings and cache/retry config
  database.py            # SQLite schema and cache helpers incl. stale reads
  categories.py
  college_fetcher.py
  social_fetcher.py
  seed_data.py
  data_cleaner.py
  templates/index.html
  static/js/{core,views,tools,app}.js
  static/css/app.css
  tests/test_app.py      # 40 passing regression tests
  requirements.txt
  pyproject.toml
  vercel.json
  .env.example
  .gitignore
  README.md
  AI_HANDOFF.md          # this file
```

## 4. Files modified so far

Latest code commit at the time of this report: `882c4e3` — `Add official watched Instagram post alerts`.

Files changed in that commit:

- `.env.example`
- `README.md`
- `app.py`
- `config.py`
- `database.py`
- `social_fetcher.py`
- `static/css/app.css`
- `static/js/core.js`
- `static/js/views.js`
- `templates/index.html`
- `tests/test_app.py`
- `vercel.json`

Previous UI privacy commit: `5d9a09d` — `Hide AI provider and feed source details from UI`. Previous code commit: `3cfffcc` — `Fix AI prompt formatting and improve news feed reliability`.

Earlier commits already on `main`:

- `f526674` — bump static cache version for UI privacy fix
- `b3596a6` — sanitize example key after rebase
- `94cc002` — checkpoint for UI privacy cleanup
- `07541e0` — checkpoint handoff report
- `6c0b14b` — deployment, OAuth and preference review fixes
- `210ab5f` — documentation and regression tests
- `d0336ac` — Mail Summarizer and hub UI restoration
- `8b508e7` — backend hardening and official social updates

## 5. Changes implemented

1. Replaced unsafe `str.format()` prompt rendering with a single `_render_prompt()` helper based on `string.Template.safe_substitute()`.
2. Converted `NOTICE_PROMPT`, `NEWS_PROMPT` and `BRIEFING_PROMPT` placeholders from `{name}` to `$name`, leaving JSON examples as literal braces.
3. Hardened AI input/response handling: non-string inputs, non-dict context, malformed model output and empty notices now degrade to local fallback results instead of raising.
4. Added bounded RSS retry logic: one short retry with exponential backoff and jitter for transient 429/5xx/connection errors; a long `Retry-After` is respected by not retrying.
5. Added `fetch_news()` returning articles plus `throttled` and `source_status`; `get_news()` remains as a backward-compatible wrapper.
6. Changed the news cache key to a canonical per-branch key independent of `limit` and `q`, so every tab, preview and briefing reuses one upstream fetch.
7. Added a per-process fetch lock and double-checked cache to prevent duplicate concurrent RSS requests.
8. Added stale-cache fallback: when providers throttle or fail, a recent cached feed is returned with `stale: true` and an honest notice instead of fabricated or sparse data.
9. Made `get_cached_value()` optionally read a recently expired entry via `allow_stale` and `stale_max_minutes`.
10. Briefing refresh now reuses the shared news cache instead of forcing a second upstream RSS fetch.
11. Added new environment variables to `.env.example` and `README.md`.
12. Removed a secret-looking value that had been placed in the uncommitted `.env.example`; the tracked template now has an empty `AI_API_KEY`.
13. Removed the Settings links that opened raw `/api/bootstrap` and `/api/health` JSON payloads in the browser.
14. Removed the configured model name from `/api/bootstrap` and `/api/health`; no deployment-side model identifier is sent to the browser.
15. Replaced all visible provider/model labels (Gemini, model name, RSS source, AI/local brief badges) with neutral labels such as "Smart summaries" and "Briefing".
16. Hid article and campus source names, sender addresses and external "original source" links from the rendered cards. The underlying feeds and summaries still work.
17. Added a regression test that scans the template and JavaScript bundles for provider/source disclosure strings and raw API payload links.
18. After rebasing onto a newer remote commit, cleared a non-placeholder `AI_API_KEY` value that had been re-added to the tracked `.env.example`; the template is empty again and the value was never displayed or copied.
19. Added official Instagram Business Discovery watching for `@mitwpuofficial` by default. No scraping, private profiles or unofficial endpoints are used.
20. Added a protected `/api/social/poll` route (GET/POST) that verifies Vercel's `Authorization: Bearer <CRON_SECRET>` header and records newly seen posts.
21. Added `social_posts` SQLite state, baseline seeding on the first successful poll, unread alert counting, and a mark-as-read endpoint.
22. Added new-post items to `/api/notifications` and included `social_alerts` in `get_stats()`, so the bell dot reacts to new posts.
23. Added a neutral "Latest post" card to the MIT-WPU Updates screen, populated from real watched posts only.
24. Added a daily Vercel Cron entry for `/api/social/poll` and documented the required Meta app permissions/Advanced Access. Stories are intentionally not supported.

## 6. Bugs identified

- **Error A:** `NOTICE_PROMPT.format()` interpreted the JSON example's `{ "tldr": ... }` as a format field, producing `KeyError: '\n  "tldr"'`.
- **Error B:** `NEWS_PROMPT.format(articles=...)` interpreted `{ "articles": ... }` as a format field, producing `KeyError: '\n  "articles"'`.
- **Error C:** `BRIEFING_PROMPT.format(context=...)` interpreted `{ "headline": ... }` as a format field, producing `KeyError: '"headline"'`.
- **Error D:** Google News RSS returned HTTP 429; the old code had no throttling status, no bounded retry, and cache keys varied by `limit`, causing repeated upstream fetches.
- **Security issue:** an uncommitted `.env.example` contained a secret-looking AI key. It was replaced with an empty placeholder and was not committed. If a key was ever committed in Git history (`f9f79c3`, and later remote commit `88f5da8`), it must be rotated.
- **UI disclosure issue:** the Settings screen linked directly to raw `/api/bootstrap` and `/api/health` payloads, and multiple views rendered provider/model/feed-source details such as Gemini model names, "Live RSS briefing", source names and sender addresses.
- **Instagram limitation:** a public profile URL is not an API connection. New-post/story notifications for `@mitwpuofficial` require authorized Meta Business Discovery; stories of accounts you do not manage are not exposed by that API.

## 7. Bugs fixed

All three prompt-formatting crashes are fixed and covered by tests that assert JSON braces remain intact. HTTP 429 is now handled with a single bounded retry, throttling metadata, cached-feed fallback and an honest API `notice`. No articles, dates or sources are fabricated. The UI no longer exposes API payload links, provider/model names, feed-source labels, sender addresses or original-source links. Official watched Instagram posts now produce neutral in-app alerts and a latest-post card without scraping or fabricating data.

## 8. Tests performed

Locally, from the repository root:

```bash
python -m py_compile app.py config.py database.py ai_summarizer.py news_fetcher.py social_fetcher.py tests/test_app.py
python -m pytest
python -c "import json; json.load(open('vercel.json', encoding='utf-8'))"
git diff --check
```

Automated checks covered:

- App import and Flask test client initialization.
- `/api/bootstrap`, `/api/news`, `/api/summarize`, `/api/briefing`, `/api/college-updates`, `/api/gmail/status`.
- Notice/news/briefing prompt rendering with mocked Gemini responses.
- Malformed AI responses and empty input fallback behavior.
- Bounded 429 retry behavior and no aggressive retry loop.
- Shared news cache across different page limits.
- Cached query search using the full feed.
- Stale cached feed preferred over fallback-only throttled results.
- Static asset endpoints and SPA fallback routes.
- UI regression scan for provider/model/source disclosure strings and raw API payload links.
- Instagram Business Discovery request shape, watch markers and exclusion of stories.
- Protected social poll authorization, baseline seeding, new-post alert creation, notification rendering and mark-as-read flow.
- `vercel.json` JSON validation and daily cron configuration.
- Secret-pattern scan of tracked text files.

## 9. Test results

- `python -m py_compile`: passed.
- `python -m pytest`: **40 passed** in about 8 seconds.
- `git diff --check`: passed (only a harmless LF→CRLF normalization warning for `.env.example`).
- Secret scan: no hardcoded key values in the working tree; only the placeholder in `README.md` and empty environment entries in `.env.example`.

## 10. Tests still pending

- Live Gemini call with a real key (not used in automated tests).
- Live Vercel deployment and production log verification.
- Live Google News throttling behavior under real deployment traffic.
- Gmail OAuth end-to-end with real Google credentials.
- LinkedIn/Instagram live posts with real authorized tokens.
- Live Meta App Review approval and a real Facebook Login token for Business Discovery.
- Live Vercel Cron invocation with `CRON_SECRET` and production log verification.

## 11. Current Git branch

`main`, tracking `origin/main`.

## 12. Latest commit hash

`882c4e3` — official watched Instagram post alerts. A checkpoint commit containing this report follows.

## 13. Working tree state

Clean at the time of writing, immediately after the code commit and before updating `AI_HANDOFF.md`.

## 14. Remaining tasks

1. Rotate any AI API key that was ever committed to Git history. Do not rewrite history or force-push without explicit approval.
2. Deploy to Vercel and check that `/static/js/core.js` and `/static/css/app.css` return real assets.
3. Configure production environment variables using names only listed below.
4. Configure a Meta app with Instagram API with Facebook Login, Advanced Access, and the Vercel variables `INSTAGRAM_API_HOST`, `INSTAGRAM_ACCESS_TOKEN`, `INSTAGRAM_USER_ID` and `CRON_SECRET` to enable live watched-post alerts.
5. Consider adding authentication before exposing mutating APIs in a public multi-user deployment.

## 15. Known problems

- Vercel SQLite uses `/tmp` fallback and is ephemeral/per-instance. This is acceptable for a read-only presentation demo, not durable multi-user storage.
- Mutating endpoints are currently unauthenticated.
- Gmail OAuth requires a stable `SECRET_KEY`; without it endpoints return `503` by design.
- The old AI key in Git history remains compromised until rotated.
- Watched-post state lives in the same ephemeral SQLite database on Vercel; a redeploy or new instance can reset seen-post history.
- Instagram does not expose other accounts' stories through Business Discovery; only published posts are supported.

## 16. Deployment status

Local tests passed. **Deployment was not verified** because no Vercel CLI, deployment URL or deployment authentication was available in this environment. `vercel.json` was inspected and retains the existing Vercel Flask architecture.

## 17. Important Vercel configuration details

- `builds` includes `static/**` with `@vercel/static` and `app.py` with `@vercel/python`.
- `routes` sends `/static/(.*)` to the static build and all other paths to `app.py`.
- `config.py` falls back to writable `/tmp` paths for SQLite and the Gmail token when the local `instance/` directory is read-only.
- Set a stable session secret in the deployment environment; otherwise Gmail OAuth remains disabled.
- Static asset URLs include a cache-busting `?v=7` query in `templates/index.html`; bump this whenever bundled JS/CSS changes.
- The latest-post card shows a neutral placeholder in MIT-WPU Updates until a watched post has been recorded.
- `crons` schedules `GET /api/social/poll` once daily at `0 6 * * *`; Hobby plans reject more frequent expressions.
- `CRON_SECRET` must be set as a Vercel environment variable before the cron can call the protected poll route; redeploy after changing it.

## 18. Environment variable names only (never values)

`AI_API_KEY`, `GEMINI_API_KEY`, `GEMINI_MODEL`, `GEMINI_FALLBACK_MODELS`, `AI_TIMEOUT_SECONDS`, `AI_MAX_INPUT_CHARS`, `SECRET_KEY`, `FLASK_DEBUG`, `PORT`, `CRON_SECRET`, `DATABASE_PATH`, `NEWS_CACHE_MINUTES`, `NEWS_STALE_MAX_MINUTES`, `NEWS_FETCH_ATTEMPTS`, `NEWS_RETRY_BASE_SECONDS`, `NEWS_RETRY_MAX_SECONDS`, `REQUEST_TIMEOUT`, `COLLEGE_CACHE_MINUTES`, `BRIEFING_CACHE_MINUTES`, `AI_CACHE_MINUTES`, `CORS_ORIGINS`, `COLLEGE_WEBSITE_URL`, `COLLEGE_NAME`, `COLLEGE_SHORT_NAME`, `COLLEGE_CITY`, `GOOGLE_CLIENT_SECRETS_FILE`, `GOOGLE_REDIRECT_URI`, `GMAIL_TOKEN_FILE`, `SOCIAL_LINKS_JSON`, `LINKEDIN_ACCESS_TOKEN`, `LINKEDIN_API_VERSION`, `LINKEDIN_AUTHOR_URNS`, `INSTAGRAM_ACCESS_TOKEN`, `INSTAGRAM_USER_ID`, `INSTAGRAM_API_HOST`, `INSTAGRAM_GRAPH_VERSION`, `INSTAGRAM_DISCOVERY_USERNAMES`, `INSTAGRAM_WATCH_LIMIT`.

## 19. Exact next steps to continue

1. Read this file and `git log -3 --oneline`.
2. Run `python -m pytest` to confirm the baseline.
3. Push the checkpoint commit if it is not already on `origin/main` (`git push origin main`, never force).
4. Ask the user to rotate the historical AI key.
5. Set the Vercel Meta/Instagram variables and `CRON_SECRET`, then deploy normally so the daily cron is registered.
6. If Vercel access is available, check runtime logs plus `/api/health`, `/api/news`, `/api/summarize`, `/api/briefing` and an authorized `/api/social/poll`.
7. If production logs still show an error, capture the exact route and message, reproduce with a mocked test, fix the root cause and add a regression test.

## 20. Potential risks another AI should avoid

- Do not revert prompt variables to `{name}` with `.format()`; that restores the production crashes.
- Do not reintroduce per-limit news cache keys or forced news refreshes inside briefing; that recreates duplicate RSS requests.
- Do not add aggressive retry loops or long sleeps; serverless execution time is limited.
- Do not commit `.env`, `credentials.json`, token files or any real key value.
- Do not force-push, rewrite shared history or delete branches.
- Do not redesign the frontend or remove existing features to make backend errors disappear.
- Do not reintroduce provider/model labels, raw API payload links, source names, sender addresses or original-source links into the UI.
- Do not scrape Instagram profiles/private endpoints or claim story notifications; Business Discovery covers posts from public professional accounts only.
- Do not expose `CRON_SECRET` in the frontend, logs, commits or responses.
- Do not claim Vercel deployment was verified unless an actual deployment/log check was performed.
