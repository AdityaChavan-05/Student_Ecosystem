import os


class Config:
    """Central configuration for the Student Ecosystem application."""

    SECRET_KEY = os.getenv(
        "SECRET_KEY",
        "development-only-change-this-key"
    )

    AI_API_KEY = os.getenv("AI_API_KEY", "").strip()

    GEMINI_MODEL = os.getenv(
        "GEMINI_MODEL",
        "gemini-3.8-flash"
    )

    COLLEGE_WEBSITE_URL = os.getenv(
        "COLLEGE_WEBSITE_URL",
        ""
    ).strip()

    FLASK_DEBUG = (
        os.getenv("FLASK_DEBUG", "false").lower()
        == "true"
    )

    SUPABASE_URL = os.getenv("SUPABASE_URL", "").strip()

    SUPABASE_KEY = os.getenv("SUPABASE_KEY", "").strip()

    NEWS_CACHE_MINUTES = int(
        os.getenv("NEWS_CACHE_MINUTES", "30")
    )

    REQUEST_TIMEOUT = int(
        os.getenv("REQUEST_TIMEOUT", "15")
    )
