
from typing import Any

import httpx

from backend.app.core.config import get_settings


SEARCH_URL = "https://api.search.tinyfish.ai"


class TinyFishError(Exception):
    """Raised when TinyFish search fails."""


async def search_external_evidence(
    query: str,
    *,
    location: str = "IN",
    language: str = "en",
    max_results: int = 10,
) -> list[dict[str, Any]]:
    """Search the web and return normalized external evidence candidates."""

    settings = get_settings()
    api_key = settings.TINYFISH_API_KEY.strip()

    if not api_key:
        raise TinyFishError("TINYFISH_API_KEY is not configured.")

    if not query.strip():
        raise ValueError("Search query cannot be empty.")

    if not 1 <= max_results <= 20:
        raise ValueError("max_results must be between 1 and 20.")

    params = {
        "query": query.strip(),
        "location": location,
        "language": language,
    }
    headers = {"X-API-Key": api_key}

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                SEARCH_URL,
                params=params,
                headers=headers,
            )
            response.raise_for_status()
            payload = response.json()

    except httpx.TimeoutException as exc:
        raise TinyFishError("TinyFish search timed out.") from exc
    except httpx.HTTPStatusError as exc:
        raise TinyFishError(
            f"TinyFish returned HTTP {exc.response.status_code}."
        ) from exc
    except httpx.RequestError as exc:
        raise TinyFishError("Could not connect to TinyFish.") from exc
    except ValueError as exc:
        raise TinyFishError("TinyFish returned invalid JSON.") from exc

    results = payload.get("results", [])

    if not isinstance(results, list):
        raise TinyFishError("Unexpected TinyFish response format.")

    normalized = []

    for item in results[:max_results]:
        if not isinstance(item, dict):
            continue

        url = item.get("url")
        title = item.get("title")
        snippet = item.get("snippet")

        if not isinstance(url, str) or not url.strip():
            continue

        normalized.append(
            {
                "source_name": item.get("site_name") or title or "Unknown source",
                "source_url": url.strip(),
                "claim": title.strip() if isinstance(title, str) else "",
                "excerpt": snippet.strip() if isinstance(snippet, str) else "",
                "source_type": "web_search",
                "published_at": None,
            }
        )

    return normalized
