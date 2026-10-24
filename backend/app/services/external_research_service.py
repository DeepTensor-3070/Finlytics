from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import urlparse


@dataclass
class ResearchSource:
    title: str
    url: str
    excerpt: str
    published_at: datetime | None = None
    source_name: str | None = None


def build_research_query(
    entity_name: str,
    topic: str = "financial risk regulatory actions litigation insolvency",
) -> str:
    entity_name = entity_name.strip()

    if not entity_name:
        raise ValueError("Entity name is required.")

    if len(entity_name) > 255:
        raise ValueError("Entity name is too long.")

    return f'"{entity_name}" {topic}'


def normalize_research_result(result: dict) -> ResearchSource | None:
    """Normalize a search result into Finlytics' internal format."""
    url = str(result.get("url") or result.get("link") or "").strip()
    title = str(result.get("title") or "").strip()
    excerpt = str(
        result.get("snippet")
        or result.get("description")
        or result.get("text")
        or ""
    ).strip()

    parsed = urlparse(url)

    if parsed.scheme != "https" or not parsed.hostname:
        return None

    if parsed.username is not None or parsed.password is not None:
        return None

    if not title or not excerpt:
        return None

    return ResearchSource(
        title=title,
        url=url,
        excerpt=excerpt,
        source_name=parsed.hostname,
    )
