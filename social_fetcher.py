"""Optional official social sources for the College Hub.

LinkedIn and Instagram do not allow scraping arbitrary profiles. This module
therefore uses only documented APIs:

- LinkedIn Posts API: pages/members the authenticated token is allowed to read
  (``r_organization_social`` or the restricted ``r_member_social`` scope).
- Instagram Graph API: a professional account the token owns/manages, or
  Business Discovery for other *professional* accounts when configured.

Without credentials this module returns no posts and only exposes the profile
shortcuts configured in ``SOCIAL_LINKS_JSON``. It never invents announcements,
dates, sources or links.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from datetime import datetime, timezone
from urllib.parse import quote, urlparse

import requests

from config import Config

logger = logging.getLogger(__name__)

SESSION = requests.Session()
SESSION.headers.update(
    {
        "User-Agent": "StudentEcosystem/2.0 (+social-updates)",
        "Accept": "application/json",
    }
)


def _iso_time(value) -> str | None:
    # LinkedIn returns epoch milliseconds; Instagram returns ISO 8601 strings.
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        seconds = value / 1000 if abs(value) >= 1e11 else value
        try:
            return datetime.fromtimestamp(seconds, tz=timezone.utc).isoformat(timespec="seconds")
        except (OverflowError, OSError, ValueError):
            return None
    text = str(value or "").strip()
    if not text:
        return None
    if text.isdigit():
        return _iso_time(int(text))
    try:
        moment = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        for pattern in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S"):
            try:
                moment = datetime.strptime(text, pattern)
                break
            except ValueError:
                continue
        else:
            return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc).isoformat(timespec="seconds")


def _clean_text(value) -> str:
    text = str(value or "")
    # LinkedIn returns hashtag/mention templates; keep the readable label.
    text = re.sub(r"\{hashtag\|\\#\|([^}]+)\}", r"#\1", text)
    # The template is {mention|URN|Display Name}; keep the display name.
    text = re.sub(
        r"\{(?:mention|organization)\|[^|}]+\|([^{}]+)\}", r"\1", text
    )
    return re.sub(r"\s+", " ", text).strip()


def _stable_id(prefix: str, value: str) -> str:
    digest = hashlib.sha1(value.encode("utf-8", "ignore")).hexdigest()[:12]
    return f"{prefix}{digest}"


def _safe_http_url(value) -> str | None:
    try:
        parsed = urlparse(str(value or ""))
        if parsed.scheme in {"http", "https"} and parsed.netloc:
            return parsed.geturl()
    except (TypeError, ValueError):
        pass
    return None


def social_links() -> list[dict]:
    """Return configured profile shortcuts, never a fabricated default."""
    raw = Config.SOCIAL_LINKS_JSON.strip()
    if not raw:
        return []

    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError):
        logger.warning("SOCIAL_LINKS_JSON is not valid JSON.")
        return []

    if isinstance(parsed, dict):
        parsed = parsed.get("links") or []

    links: list[dict] = []
    for entry in parsed if isinstance(parsed, list) else []:
        if isinstance(entry, str):
            parts = [part.strip() for part in entry.split("|", 1)]
            candidate = {
                "label": parts[0] or "Official profile",
                "url": parts[1] if len(parts) == 2 else parts[0],
            }
        elif isinstance(entry, dict):
            candidate = dict(entry)
        else:
            continue

        url = _safe_http_url(candidate.get("url") or candidate.get("href"))
        if not url:
            continue
        platform = str(
            candidate.get("platform")
            or ("linkedin" if "linkedin." in url else "instagram" if "instagram." in url else "web")
        ).lower()
        links.append(
            {
                "label": str(candidate.get("label") or platform.title())[:80],
                "url": url,
                "platform": platform,
            }
        )
    return links[:12]


def social_status() -> dict:
    return {
        "linkedin": bool(Config.LINKEDIN_ACCESS_TOKEN and Config.LINKEDIN_AUTHOR_URNS),
        "instagram": bool(Config.INSTAGRAM_ACCESS_TOKEN and Config.INSTAGRAM_USER_ID),
        "links": social_links(),
        "modes": {
            "linkedin": "Posts API (official)",
            "instagram": "Instagram Graph API (official)",
        },
    }


def _normalise_urn(value: str) -> str:
    value = value.strip()
    if value.startswith("urn:li:"):
        return value
    if re.fullmatch(r"\d+", value):
        return f"urn:li:organization:{value}"
    return value


def _linkedin_label(urn: str) -> str:
    return f"LinkedIn · {urn.rsplit(':', 1)[-1]}"


def _linkedin_post_url(post_id: str) -> str:
    """Use LinkedIn's documented update URL only for known post URNs."""
    if re.fullmatch(r"urn:li:(?:share|ugcPost):\d+", post_id):
        return f"https://www.linkedin.com/feed/update/{post_id}/"
    return ""


def fetch_linkedin_updates(limit: int = 8) -> list[dict]:
    if not Config.LINKEDIN_ACCESS_TOKEN or not Config.LINKEDIN_AUTHOR_URNS:
        return []

    headers = {
        "Authorization": f"Bearer {Config.LINKEDIN_ACCESS_TOKEN}",
        "Linkedin-Version": Config.LINKEDIN_API_VERSION,
        "X-Restli-Protocol-Version": "2.0.0",
        "X-RestLi-Method": "FINDER",
    }
    updates: list[dict] = []
    seen: set[str] = set()

    for raw_urn in Config.LINKEDIN_AUTHOR_URNS[:5]:
        urn = _normalise_urn(raw_urn)
        try:
            response = SESSION.get(
                "https://api.linkedin.com/rest/posts",
                params={
                    "q": "author",
                    "author": urn,
                    "count": max(1, min(limit, 20)),
                    "sortBy": "CREATED",
                },
                headers=headers,
                timeout=Config.REQUEST_TIMEOUT,
            )
            response.raise_for_status()
            payload = response.json() or {}
        except Exception:
            # Never log the response URL: it can carry credentials in errors.
            logger.info("LinkedIn Posts API request failed for a configured author.")
            continue

        for post in payload.get("elements") or []:
            if not isinstance(post, dict):
                continue
            text = _clean_text(post.get("commentary"))
            if not text:
                continue
            post_id = str(post.get("id") or "")
            key = post_id or text[:120]
            if key in seen:
                continue
            seen.add(key)
            published_at = _iso_time(post.get("publishedAt") or post.get("createdAt"))
            link = _linkedin_post_url(post_id)
            updates.append(
                {
                    "id": _stable_id("social_linkedin_", key),
                    "title": text[:220],
                    "description": text[:1200],
                    "tldr": text[:260],
                    "category": "Social",
                    "source": _linkedin_label(urn),
                    "link": link,
                    "published_at": published_at,
                    "tags": ["social", "linkedin"],
                    "origin": "linkedin",
                    "curated": False,
                    "what_to_do": [],
                }
            )
    return updates[:limit]


def _instagram_base() -> str:
    host = Config.INSTAGRAM_API_HOST.strip().rstrip("/")
    if not host.startswith(("http://", "https://")):
        host = f"https://{host}"
    version = Config.INSTAGRAM_GRAPH_VERSION.strip("/")
    return f"{host}/{version}"


def _normalise_instagram_media(item: dict, source: str) -> dict | None:
    if not isinstance(item, dict):
        return None
    caption = _clean_text(item.get("caption"))
    if not caption:
        return None
    link = _safe_http_url(item.get("permalink"))
    if not link:
        return None
    key = str(item.get("id") or link)
    return {
        "id": _stable_id("social_instagram_", key),
        "title": caption[:220],
        "description": caption[:1200],
        "tldr": caption[:260],
        "category": "Social",
        "source": source,
        "link": link,
        "published_at": _iso_time(item.get("timestamp")),
        "tags": ["social", "instagram"],
        "origin": "instagram",
        "curated": False,
        "what_to_do": [],
    }


def fetch_instagram_updates(limit: int = 8) -> list[dict]:
    if not Config.INSTAGRAM_ACCESS_TOKEN or not Config.INSTAGRAM_USER_ID:
        return []

    base = _instagram_base()
    params = {
        "fields": "id,caption,timestamp,permalink",
        "limit": max(1, min(limit, 25)),
        "access_token": Config.INSTAGRAM_ACCESS_TOKEN,
    }
    results: list[dict] = []

    try:
        response = SESSION.get(
            f"{base}/{Config.INSTAGRAM_USER_ID}/media",
            params=params,
            timeout=Config.REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        for item in (response.json() or {}).get("data") or []:
            update = _normalise_instagram_media(item, "Instagram · connected account")
            if update:
                results.append(update)
    except Exception:
        logger.info("Instagram media request failed for the connected account.")

    for username in Config.INSTAGRAM_DISCOVERY_USERNAMES[:4]:
        fields = (
            "business_discovery.username("
            f"{quote(username, safe='')})"
            "{{id,media{{id,caption,timestamp,permalink}}}}"
        )
        try:
            response = SESSION.get(
                f"{base}/{Config.INSTAGRAM_USER_ID}",
                params={
                    "fields": fields,
                    "access_token": Config.INSTAGRAM_ACCESS_TOKEN,
                },
                timeout=Config.REQUEST_TIMEOUT,
            )
            response.raise_for_status()
            discovery = ((response.json() or {}).get("business_discovery") or {})
            media = discovery.get("media") or {}
            for item in media.get("data") or []:
                update = _normalise_instagram_media(item, f"Instagram @{username}")
                if update:
                    results.append(update)
        except Exception:
            logger.info("Instagram Business Discovery failed for one configured account.")

    seen: set[str] = set()
    unique = []
    for item in results:
        key = item.get("link") or item.get("id")
        if key and key not in seen:
            seen.add(key)
            unique.append(item)
    return unique[:limit]


def get_social_updates(limit: int = 8) -> dict:
    """Fetch configured official social posts with graceful degradation."""
    limit = max(1, min(int(limit or 8), 20))
    updates = [*fetch_linkedin_updates(limit), *fetch_instagram_updates(limit)]
    updates.sort(key=lambda item: item.get("published_at") or "", reverse=True)

    return {
        "count": len(updates[:limit]),
        "updates": updates[:limit],
        "profiles": social_links(),
        "status": social_status(),
        "note": (
            "Posts come only from officially authorised LinkedIn/Instagram APIs. "
            "Personal profiles and unmanaged pages cannot be scraped."
        ),
    }
