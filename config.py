
"""Central configuration for the Student Ecosystem application.

Every value can be supplied through environment variables (or a local
.env file). Sensible defaults keep the application fully functional
without any external credentials.
"""

from __future__ import annotations

import os
import secrets
import tempfile
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
    """Return a writable SQLite path."""
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
        return str(Path(tempfile.gettempdir()) / local.name)

    return str(local)


def _default_token_path() -> str:
    """Return a writable OAuth token path (serverless hosts need /tmp)."""
    configured = os.getenv("GMAIL_TOKEN_FILE", "").strip()
    if configured:
        return configured

    local = BASE_DIR / "instance" / "gmail_token.json"
    try:
        local.parent.mkdir(parents=True, exist_ok=True)
        probe = local.parent / ".write_probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
    except OSError:
        return str(Path(tempfile.gettempdir()) / local.name)

    return str(local)


class Config:
    """Application configuration."""

    # Flask ---------------------------------------------------------------
    # A random per-process fallback is deliberately safer than a predictable
    # default. Set SECRET_KEY explicitly when sessions must survive restarts.
    SECRET_KEY = os.getenv("SECRET_KEY", "").strip() or secrets.token_urlsafe(32)
    DEBUG = _env_bool("FLASK_DEBUG", False)
    MAX_CONTENT_LENGTH = 6 * 1024 * 1024
    JSON_SORT_KEYS = False

    # Gmail OAuth ---------------------------------------------------------
    GOOGLE_CLIENT_SECRETS_FILE = os.getenv(
        "GOOGLE_CLIENT_SECRETS_FILE",
        str(BASE_DIR / "credentials.json"),
    )
    GOOGLE_REDIRECT_URI = os.getenv(
        "GOOGLE_REDIRECT_URI",
        "http://127.0.0.1:5000/auth/google/callback",
    )
    GMAIL_TOKEN_FILE = _default_token_path()

    # Storage -------------------------------------------------------------
    DATABASE_PATH = _default_database_path()

    # AI ------------------------------------------------------------------
    AI_API_KEY = os.getenv(
        "AI_API_KEY",
        os.getenv("GEMINI_API_KEY", ""),
    ).strip()

    GEMINI_MODEL = os.getenv(
        "GEMINI_MODEL",
        "gemini-2.5-flash",
    ).strip()

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
        "COLLEGE_WEBSITE_URL",
        "https://mitwpu.edu.in/",
    ).strip()

    COLLEGE_NAME = os.getenv(
        "COLLEGE_NAME",
        "MIT World Peace University",
    ).strip()

    COLLEGE_SHORT_NAME = os.getenv(
        "COLLEGE_SHORT_NAME",
        "MIT-WPU",
    ).strip()

    COLLEGE_CITY = os.getenv(
        "COLLEGE_CITY",
        "Pune, Maharashtra",
    ).strip()

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

    # Social sources -------------------------------------------------------
    # Credentials are optional. Without them the UI shows official profile
    # shortcuts only; it never invents posts.
    SOCIAL_LINKS_JSON = os.getenv("SOCIAL_LINKS_JSON", "").strip()
    SOCIAL_CACHE_MINUTES = _env_int("SOCIAL_CACHE_MINUTES", 30)

    LINKEDIN_ACCESS_TOKEN = os.getenv("LINKEDIN_ACCESS_TOKEN", "").strip()
    LINKEDIN_API_VERSION = os.getenv("LINKEDIN_API_VERSION", "202601").strip()
    LINKEDIN_AUTHOR_URNS = tuple(
        item.strip()
        for item in os.getenv("LINKEDIN_AUTHOR_URNS", "").split(",")
        if item.strip()
    )

    INSTAGRAM_ACCESS_TOKEN = os.getenv("INSTAGRAM_ACCESS_TOKEN", "").strip()
    INSTAGRAM_USER_ID = os.getenv("INSTAGRAM_USER_ID", "").strip()
    INSTAGRAM_GRAPH_VERSION = os.getenv("INSTAGRAM_GRAPH_VERSION", "v26.0").strip()
    INSTAGRAM_API_HOST = os.getenv(
        "INSTAGRAM_API_HOST", "graph.instagram.com"
    ).strip()
    INSTAGRAM_DISCOVERY_USERNAMES = tuple(
        item.strip().lstrip("@")
        for item in os.getenv("INSTAGRAM_DISCOVERY_USERNAMES", "").split(",")
        if item.strip()
    )

    # CORS ----------------------------------------------------------------
    # Same-origin is the default; the SPA does not need wildcard CORS. Add
    # explicit origins only when a separate frontend is deployed.
    CORS_ORIGINS = [
        origin.strip()
        for origin in os.getenv("CORS_ORIGINS", "").split(",")
        if origin.strip()
    ]
