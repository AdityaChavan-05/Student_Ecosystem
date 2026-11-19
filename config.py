"""Central configuration for the Student Ecosystem application.

Every value can be supplied through environment variables (or a local
``.env`` file). Sensible defaults keep the application fully functional
without any external credentials: the database is local SQLite, feeds fall
back to curated content and AI summaries fall back to a deterministic
extractive summarizer.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent

# Load .env once, without overriding real environment variables.
load_dotenv(BASE_DIR / ".env", override=False)


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


def _default_database_path() -> str:
    """Return a writable SQLite path.

    Locally the database lives beside the app. On read-only hosts (notably
    Vercel serverless functions) that directory cannot be created, so fall
    back to the system temp directory. An explicit ``DATABASE_PATH`` is always
    respected.
    """
    configured = os.getenv("DATABASE_PATH", "").strip()
    if configured:
        return configured

    local = BASE_DIR / "instance" / "student_ecosystem.db"
    try:
        local.parent.mkdir(parents=True, exist_ok=True)
        probe = local.parent / ".write_probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
    except OSError:
        import tempfile

        return str(Path(tempfile.gettempdir()) / local.name)
    return str(local)


class Config:
    """Application configuration."""

    # Flask ---------------------------------------------------------------
    SECRET_KEY = os.getenv("SECRET_KEY", "student-ecosystem-dev-key")
    DEBUG = _env_bool("FLASK_DEBUG", False)
    MAX_CONTENT_LENGTH = 6 * 1024 * 1024  # 6 MB upload cap
    JSON_SORT_KEYS = False

    # Storage -------------------------------------------------------------
    DATABASE_PATH = _default_database_path()

    # AI ------------------------------------------------------------------
    AI_API_KEY = os.getenv("AI_API_KEY", os.getenv("GEMINI_API_KEY", "")).strip()
    GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip()
    # Ordered fallbacks used when the primary model is unavailable.
    GEMINI_FALLBACK_MODELS = tuple(
        model.strip()
        for model in os.getenv(
            "GEMINI_FALLBACK_MODELS",
            "gemini-2.5-flash,gemini-2.0-flash,gemini-1.5-flash",
        ).split(",")
        if model.strip()
    )
    AI_TIMEOUT_SECONDS = _env_int("AI_TIMEOUT_SECONDS", 40)
    AI_MAX_INPUT_CHARS = _env_int("AI_MAX_INPUT_CHARS", 14000)

    # Campus feed ---------------------------------------------------------
    COLLEGE_WEBSITE_URL = os.getenv(
        "COLLEGE_WEBSITE_URL", "https://mitwpu.edu.in/"
    ).strip()
    COLLEGE_NAME = os.getenv("COLLEGE_NAME", "MIT World Peace University").strip()
    COLLEGE_SHORT_NAME = os.getenv("COLLEGE_SHORT_NAME", "MIT-WPU").strip()
    COLLEGE_CITY = os.getenv("COLLEGE_CITY", "Pune, Maharashtra").strip()

    # Caching -------------------------------------------------------------
    NEWS_CACHE_MINUTES = _env_int("NEWS_CACHE_MINUTES", 30)
    COLLEGE_CACHE_MINUTES = _env_int("COLLEGE_CACHE_MINUTES", 20)
    AI_CACHE_MINUTES = _env_int("AI_CACHE_MINUTES", 60 * 24 * 7)
    BRIEFING_CACHE_MINUTES = _env_int("BRIEFING_CACHE_MINUTES", 60 * 6)

    # Feeds ---------------------------------------------------------------
    REQUEST_TIMEOUT = _env_int("REQUEST_TIMEOUT", 12)
    DEFAULT_NEWS_LIMIT = 9
    MAX_NEWS_LIMIT = 24

    # Server --------------------------------------------------------------
    PORT = _env_int("PORT", 5000)

    # CORS: comma separated origins. "*" allows any origin (read-only usage).
    CORS_ORIGINS = [
        origin.strip()
        for origin in os.getenv("CORS_ORIGINS", "*").split(",")
        if origin.strip()
    ]
