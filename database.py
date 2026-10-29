import logging
import os

from datetime import datetime, timedelta, timezone

from supabase import create_client


logger = logging.getLogger(__name__)

CACHE_TABLE = "app_cache"

_supabase_client = None


def get_supabase_client():
    """
    Create and reuse the Supabase client.

    Returns None when credentials have not been configured.
    """
    global _supabase_client

    if _supabase_client is not None:
        return _supabase_client

    supabase_url = os.getenv("SUPABASE_URL", "").strip()
    supabase_key = os.getenv("SUPABASE_KEY", "").strip()

    if not supabase_url or not supabase_key:
        return None

    try:
        _supabase_client = create_client(
            supabase_url,
            supabase_key,
        )

        return _supabase_client

    except Exception:
        logger.warning(
            "Supabase client initialization failed."
        )
        return None


def get_cached_value(cache_key):
    """
    Retrieve an unexpired value from the Supabase cache.

    Returns None when the value is missing, expired,
    or the database is not configured.
    """
    if not cache_key:
        return None

    client = get_supabase_client()

    if client is None:
        return None

    try:
        now = datetime.now(timezone.utc).isoformat()

        response = (
            client.table(CACHE_TABLE)
            .select("value, expires_at")
            .eq("cache_key", str(cache_key))
            .gt("expires_at", now)
            .limit(1)
            .execute()
        )

        rows = response.data or []

        if not rows:
            return None

        return rows[0].get("value")

    except Exception:
        logger.warning(
            "Could not read the application cache."
        )
        return None


def set_cached_value(cache_key, value, ttl_minutes=30):
    """
    Store a JSON-compatible value in Supabase.

    The cache entry expires after ttl_minutes.

    Returns True when the database accepts the write,
    or False when caching is unavailable.
    """
    if not cache_key:
        return False

    client = get_supabase_client()

    if client is None:
        return False

    try:
        ttl_minutes = max(1, int(ttl_minutes))

        expires_at = (
            datetime.now(timezone.utc)
            + timedelta(minutes=ttl_minutes)
        ).isoformat()

        record = {
            "cache_key": str(cache_key),
            "value": value,
            "expires_at": expires_at,
        }

        (
            client.table(CACHE_TABLE)
            .upsert(record, on_conflict="cache_key")
            .execute()
        )

        return True

    except Exception:
        logger.warning(
            "Could not save data to the application cache."
        )
        return False


def is_database_configured():
    """Check whether Supabase credentials are available."""
    return bool(
        os.getenv("SUPABASE_URL", "").strip()
        and os.getenv("SUPABASE_KEY", "").strip()
    )
