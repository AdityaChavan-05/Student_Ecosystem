# Student Ecosystem

A calm, high-signal daily companion for engineering students at **MIT World Peace University (MIT-WPU), Pune**. It pulls campus updates, hackathons and opportunities, engineering/AI news, and turns emails or notices into structured summaries — all connected to one task hub, one academic vault and one saved library.

Built as a zero-build **Flask + SQLite + vanilla JavaScript** single-page app. No Node toolchain, no external database and no API keys are required: everything has a resilient fallback.

---

## What is inside

| Module | What it does |
| --- | --- |
| **Overview** | Greeting, daily AI briefing, live stats, focus ring, next deadlines, quick actions. |
| **MIT-WPU Updates** | Scrapes the official MIT-WPU site (home, notices, news, events), classifies each item, extracts deadlines and writes a TL;DR + "what to do", then merges a curated campus guide when the site is unreachable. |
| **Hackathons & Events** | 20 curated, roll-forward opportunities (hackathons, contests, open source, fellowships, workshops, summits, internships) with deadline, mode, location, prize/perks, "why it's worth it", filters, saving and one-click deadline tasks. |
| **AI News & Briefings** | Multi-source RSS (Google News, Bing News, major engineering publications) filtered by branch, deduplicated and ranked so stories with real summaries surface first, then distilled into TL;DR + takeaways. Headline-only feeds are labelled honestly instead of being padded. Falls back to a curated reading list. |
| **Mail Summarizer** | Paste a notice or upload `.eml` / `.txt` (drag-and-drop supported). Returns TL;DR, deadlines, action items, category, urgency and tags; saves every summary and converts any action into a task. |
| **Academic Vault** | 28 seeded resources plus your own links/notes: subjects, branch scope, types (course, notes, video, practice, tool), starring, search and filters. |
| **Task Hub** | Kanban board (To do / In progress / Done) with drag-and-drop, priorities, due dates, tags, overdue tracking and source links back to campus notices, opportunities, news and mail summaries. |
| **Saved** | One library for bookmarked campus updates, opportunities, briefings and summaries. |
| **Settings** | Profile, branch, year, semester, goal, and a live status board for AI, campus feed and storage. |

Global touches: instant search per view, **Ctrl/Cmd + K** command palette (`/` also works), notifications panel for imminent deadlines, skeleton loaders, empty states, toasts, keyboard and screen-reader labels, reduced-motion support, dark/light themes (persisted, respects OS preference), responsive laptop/mobile layouts and a mobile bottom navigation bar.

---

## Quick start

```bash
# 1. Create and activate a virtual environment
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS / Linux

# 2. Install dependencies
pip install -r requirements.txt

# 3. (Optional) configure environment — everything works without it
copy .env.example .env        # Windows
# cp .env.example .env        # macOS / Linux

# 4. Run
python app.py
```

Open <http://localhost:5000>. The SQLite database (`instance/student_ecosystem.db`) is created and seeded automatically on first request.

### Optional: enable Gemini summaries

Add a key to `.env`:

```dotenv
AI_API_KEY=your-google-ai-studio-key
GEMINI_MODEL=gemini-2.5-flash
```

Without a key (or when the API errors, rate-limits or times out) the app transparently uses its deterministic extractive summarizer. The UI labels the mode honestly everywhere ("Gemini summary" vs "Smart local summary").

---

## Configuration

All settings live in `.env` (see `.env.example`) and are read by `config.py`.

| Variable | Default | Purpose |
| --- | --- | --- |
| `SECRET_KEY` | dev key | Flask session signing. Set a real value in production. |
| `FLASK_DEBUG` | `false` | Flask debug mode. |
| `PORT` | `5000` | Development server port. |
| `DATABASE_PATH` | `instance/student_ecosystem.db` | SQLite file. Auto-falls back to a temp dir on read-only hosts such as Vercel. |
| `AI_API_KEY` | empty | Google AI Studio key (`GEMINI_API_KEY` also accepted). |
| `GEMINI_MODEL` | `gemini-2.5-flash` | Primary model. |
| `GEMINI_FALLBACK_MODELS` | `gemini-2.5-flash,gemini-2.0-flash,gemini-1.5-flash` | Ordered fallbacks. |
| `AI_TIMEOUT_SECONDS` | `40` | Per-call AI timeout. |
| `AI_MAX_INPUT_CHARS` | `14000` | Input truncation before sending to the model. |
| `COLLEGE_WEBSITE_URL` | `https://mitwpu.edu.in/` | Campus source. |
| `COLLEGE_NAME` / `COLLEGE_SHORT_NAME` / `COLLEGE_CITY` | MIT-WPU values | Display metadata. |
| `REQUEST_TIMEOUT` | `12` | Outbound HTTP timeout for feeds and scraping. |
| `NEWS_CACHE_MINUTES` | `30` | News cache TTL. |
| `COLLEGE_CACHE_MINUTES` | `20` | Campus cache TTL. |
| `BRIEFING_CACHE_MINUTES` | `360` | Daily briefing cache TTL. |
| `AI_CACHE_MINUTES` | `10080` | AI result cache TTL (7 days). |
| `CORS_ORIGINS` | `*` | Comma-separated allowed origins. |

No secrets are hard-coded; the repository ships only safe defaults.

---

## How the fallbacks work

Every external dependency has a graceful degradation path:

1. **Campus feed** — MIT-WPU pages are fetched in parallel with a timeout and parsed with BeautifulSoup. If every page fails, a curated 12-item campus guide (with relative deadlines) is returned and clearly labelled "Curated campus guide" in the UI.
2. **Opportunities** — seeded curated listings with deadlines rolled forward automatically so the radar never goes stale or empty.
3. **News** — Google News RSS + Bing News RSS + publication feeds are fetched together, deduplicated, branch-filtered and ranked by recency plus real summary text. Publication feeds are fetched in parallel so briefs have substance; when a feed only carries a headline, the card says so. A curated reading list fills any remaining gap.
4. **AI** — Gemini with model-level fallbacks; on any failure the deterministic summarizer (sentence scoring, date extraction, action-verb detection, category/urgency/tag inference) takes over. Summaries are cached in SQLite.
5. **Storage** — local SQLite with WAL mode; no Supabase or cloud account needed.
6. **Uploads** — `.eml` is parsed with the standard library (subject/from/plain-text body extracted), `.txt`/`.md` are read directly, PDFs via `pypdf` when available. Files are processed in memory; nothing is written to disk.

---

## API

All endpoints return JSON. Errors use `{"error": "..."}` with an appropriate status code.

| Method | Endpoint | Description |
| --- | --- | --- |
| `GET` | `/api/health` | Liveness, AI mode, model, storage. |
| `GET` | `/api/bootstrap` | Profile, branches, college metadata, features, stats, today. |
| `GET` / `PATCH` | `/api/profile` | Read or update name, branch, year, semester, goal. |
| `GET` | `/api/branches` | Available branch list and mappings. |
| `GET` | `/api/stats` | Aggregate counts (tasks, overdue, due this week, bookmarks, summaries, vault, opportunities). |
| `GET` | `/api/college-updates?limit=&refresh=` | Campus feed with categories and live/curated status. |
| `GET` | `/api/opportunities?track=&mode=&deadline=&saved=&q=` | Opportunity radar. |
| `GET` | `/api/news?branch=&limit=&refresh=` | Summarized news briefings. |
| `GET` | `/api/briefing?refresh=` | Daily briefing generated from live context. |
| `POST` | `/api/summarize` | JSON `{text, subject, sender, create_task}` **or** multipart file upload. |
| `GET` / `POST` | `/api/summaries` | List saved summaries / summarize a post body. |
| `DELETE` | `/api/summaries/<id>` | Delete a summary. |
| `POST` | `/api/summaries/<id>/task` | Convert a summary into a task. |
| `GET` / `POST` | `/api/tasks` | List (`status`, `priority`, `q`) or create tasks. |
| `PATCH` / `DELETE` | `/api/tasks/<id>` | Update (title, notes, due date, priority, status, tags) or delete. |
| `GET` / `POST` | `/api/vault` | List (`subject`, `branch`, `type`, `q`) or add resources. |
| `PATCH` / `DELETE` | `/api/vault/<id>` | Update or delete a resource. |
| `GET` / `POST` | `/api/bookmarks` | List or toggle a bookmark (`item_key` toggles). |
| `DELETE` | `/api/bookmarks/<id>` | Remove a bookmark. |
| `GET` | `/api/search?q=` | Cross-entity search for the command palette. |
| `GET` | `/api/notifications` | Deadlines needing attention. |
| `GET` | `/manifest.webmanifest` | PWA manifest. |
| `GET` | `/favicon.ico`, `/static/*` | Icons and assets. |

Legacy paths `/news`, `/college`, `/opportunities`, `/mail`, `/vault`, `/tasks` redirect (302) into the SPA hash routes.

---

## Project structure

```
Student_Ecosystem-main/
├── app.py               # Flask app, routes, JSON API, upload parsing, error handling
├── config.py            # Environment-driven configuration with safe defaults
├── database.py          # SQLite schema, migrations and all CRUD helpers
├── seed_data.py         # Curated campus guide, opportunities, vault resources, news fallback
├── ai_summarizer.py     # Gemini client + fallback, notice/news/briefing summarization
├── college_fetcher.py   # Parallel MIT-WPU scraping, classification, curated merge
├── news_fetcher.py      # Multi-source RSS, dedupe, branch filtering
├── categories.py        # Branch mappings and keyword routing
├── data_cleaner.py      # Text cleaning helpers
├── templates/index.html # SPA shell, icon sprite, all views
├── static/css/app.css   # Design system, dark/light, responsive, animations
├── static/js/core.js    # State, API client, router, palette, toasts, theme
├── static/js/views.js   # Overview, campus, opportunities, news, saved renderers
├── static/js/tools.js   # Mail, vault, tasks, settings, action handlers
├── static/js/app.js     # Boot sequence and event wiring
├── static/favicon.svg
├── instance/            # SQLite database (created at runtime, git-ignored)
├── tests/test_app.py    # End-to-end API tests
├── requirements.txt
└── .env.example
```

---

## Tests

```bash
pip install pytest
pytest
```

The suite uses a temporary SQLite database, so it never touches your real data. It exercises health, bootstrap, profile, campus, opportunities, news, briefing, search, notifications, the full mail summarizer (JSON + `.txt` + `.eml` uploads), summaries-to-task conversion, task CRUD/validation, vault CRUD, bookmarks, static assets and SPA routes.

Manual smoke test after starting the server:

- `http://localhost:5000/api/health` → `{"status":"ok", ...}`
- Try **Mail Summarizer → Load sample notice → Summarize notice**
- Add a task, drag it between columns, bookmark an opportunity, run **Ctrl/Cmd + K**, toggle the theme, resize to a phone width.

---

## Deployment

### Render / Railway / Fly.io / any VM

```bash
gunicorn -w 2 -b 0.0.0.0:8000 app:app
```

Set `SECRET_KEY`, keep `DATABASE_PATH` on a persistent volume (e.g. `/data/student_ecosystem.db`), and optionally add `AI_API_KEY`.

### Vercel

`vercel.json` routes every request to the Flask app, which serves the SPA and static assets itself. Serverless filesystems are read-only apart from `/tmp`; `config.py` detects this automatically and falls back to a temp-dir SQLite file, so no extra configuration is needed. Set `DATABASE_PATH` explicitly only if you want a different location.

Note that `/tmp` is ephemeral between cold starts; for durable data deploy on a host with a persistent disk, or point `DATABASE_PATH` at a mounted volume.

### Docker (optional)

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ENV PORT=8000
EXPOSE 8000
CMD ["gunicorn", "-w", "2", "-b", "0.0.0.0:8000", "app:app"]
```

---

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| "Curated campus guide" badge | The MIT-WPU site was unreachable or changed structure. The app stays useful; update `COLLEGE_WEBSITE_URL` or selectors in `college_fetcher.py` if needed. |
| "Smart local summaries" | No `AI_API_KEY`, or Gemini was rate-limited/timed out. Everything still works. |
| News looks old | Feeds are cached for `NEWS_CACHE_MINUTES`; press **Refresh** or lower the TTL. |
| Database reset | Delete `instance/student_ecosystem.db`; it is recreated and reseeded on the next request. |
| Port already in use | Set `PORT=5001` in `.env` or run `flask --app app run --port 5001`. |

---

## Scope and honesty

The campus scraper targets the public MIT-WPU website and is intentionally defensive: it never invents notices. When it cannot read the site, curated guide items are labelled as such. Opportunities are curated seeds with deadlines rolled forward; always confirm details on the official page before applying. AI output can be wrong — the UI keeps the original source one click away.
