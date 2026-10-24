
import asyncio
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any
from urllib.parse import urlparse

import httpx
import pymupdf
from bs4 import BeautifulSoup


MAX_PAGE_BYTES = 2_000_000
MAX_PDF_PAGES = 30
MAX_EXTRACTED_CHARS = 12_000
REQUEST_TIMEOUT = 15.0

ERROR_INDICATORS = (
    "the file you are looking for is not available",
    "sorry for your inconvenience",
    "page not found",
    "404 not found",
    "access denied",
)


def _parse_date(value: str | None) -> datetime | None:
    if not value:
        return None

    value = value.strip()

    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except ValueError:
        pass

    try:
        parsed = parsedate_to_datetime(value)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except (TypeError, ValueError, OverflowError):
        return None


def _extract_publication_date(soup: BeautifulSoup) -> datetime | None:
    selectors = [
        ("meta", {"property": "article:published_time"}),
        ("meta", {"name": "datePublished"}),
        ("meta", {"name": "pubdate"}),
        ("meta", {"name": "publication_date"}),
        ("meta", {"name": "date"}),
        ("meta", {"itemprop": "datePublished"}),
        ("time", {"itemprop": "datePublished"}),
    ]

    for tag_name, attrs in selectors:
        tag = soup.find(tag_name, attrs=attrs)
        if not tag:
            continue

        value = tag.get("content") or tag.get("datetime")
        if not value:
            value = tag.get_text(" ", strip=True)

        parsed = _parse_date(value)
        if parsed:
            return parsed

    # Inspect JSON-LD structured metadata.
    for script in soup.find_all(
        "script",
        attrs={"type": "application/ld+json"},
    ):
        raw = script.string or script.get_text()

        match = re.search(
            r'"datePublished"\s*:\s*"([^"]+)"',
            raw,
        )
        if match:
            parsed = _parse_date(match.group(1))
            if parsed:
                return parsed

    return None


def _extract_pdf(pdf_bytes: bytes) -> dict[str, Any]:
    """Extract text from a PDF held in memory."""

    try:
        with pymupdf.open(stream=pdf_bytes, filetype="pdf") as document:
            if document.is_encrypted:
                return {
                    "title": None,
                    "excerpt": None,
                    "published_at": None,
                    "page_count": len(document),
                    "pages_extracted": 0,
                    "extraction_status": "encrypted_pdf",
                }

            metadata = document.metadata or {}
            page_count = len(document)

            text_parts = []
            pages_to_read = min(page_count, MAX_PDF_PAGES)

            for page in document[:pages_to_read]:
                page_text = page.get_text("text")
                if page_text:
                    text_parts.append(page_text)

            full_text = re.sub(
                r"\s+",
                " ",
                " ".join(text_parts),
            ).strip()

            title = (metadata.get("title") or "").strip() or None

            # PDF creation metadata is not necessarily the publication date.
            published_at = None

            return {
                "title": title,
                "excerpt": full_text[:MAX_EXTRACTED_CHARS] or None,
                "published_at": published_at,
                "page_count": page_count,
                "pages_extracted": pages_to_read,
                "extraction_status": (
                    "extracted" if full_text else "empty_document"
                ),
            }

    except Exception as exc:
        # Malformed or unreadable PDF bytes should not be treated as evidence.
        return {
            "title": None,
            "excerpt": None,
            "published_at": None,
            "page_count": None,
            "pages_extracted": 0,
            "extraction_status": "invalid_pdf",
            "error": str(exc),
        }


def _base_result(
    final_url: str,
    content_type: str,
    status: str,
    **extra: Any,
) -> dict[str, Any]:
    """Build a consistent extraction result."""
    return {
        "final_url": final_url,
        "content_type": content_type,
        "title": None,
        "excerpt": None,
        "published_at": None,
        "extraction_status": status,
        **extra,
    }


def _looks_like_error_page(title: str | None, text: str) -> bool:
    """Detect common server error pages using conservative text indicators."""
    combined = f"{title or ''} {text}".casefold()
    return any(indicator in combined for indicator in ERROR_INDICATORS)


async def extract_source_page(url: str) -> dict[str, Any]:
    """Fetch an HTTPS source and extract HTML, PDF, or plain-text content.

    This function extracts content only. It does not establish source
    authenticity, verify a claim, or prove that the content is trustworthy.
    """

    parsed_url = urlparse(url)

    if (
        parsed_url.scheme.casefold() != "https"
        or not parsed_url.hostname
        or parsed_url.username is not None
        or parsed_url.password is not None
        or any(char.isspace() for char in url)
    ):
        raise ValueError("Only valid HTTPS source URLs are allowed.")

    requested_pdf = parsed_url.path.casefold().endswith(".pdf")

    headers = {
        "User-Agent": "FinlyticsEvidenceBot/0.1",
        "Accept": "text/html,application/xhtml+xml,application/pdf,text/plain",
    }

    async with httpx.AsyncClient(
        timeout=REQUEST_TIMEOUT,
        follow_redirects=True,
        max_redirects=5,
        headers=headers,
    ) as client:
        async with client.stream("GET", url) as response:
            response.raise_for_status()

            content_type = response.headers.get(
                "content-type", ""
            ).lower()

            chunks: list[bytes] = []
            total_bytes = 0

            async for chunk in response.aiter_bytes():
                total_bytes += len(chunk)

                if total_bytes > MAX_PAGE_BYTES:
                    raise ValueError(
                        "Source exceeds the 2 MB download limit."
                    )

                chunks.append(chunk)

            body = b"".join(chunks)
            final_url = str(response.url)

    final_parsed = urlparse(final_url)

    # Do not follow redirects to non-HTTPS destinations as accepted evidence.
    if (
        final_parsed.scheme.casefold() != "https"
        or not final_parsed.hostname
        or final_parsed.username is not None
        or final_parsed.password is not None
    ):
        return _base_result(
            final_url,
            content_type,
            "unsafe_redirect",
            error="The source redirected to an invalid or non-HTTPS URL.",
        )

    # Identify PDFs by their actual file signature, not the URL alone.
    has_pdf_signature = body.lstrip().startswith(b"%PDF-")
    declares_pdf = "application/pdf" in content_type

    if has_pdf_signature:
        result = await asyncio.to_thread(_extract_pdf, body)
        return {
            "final_url": final_url,
            "content_type": content_type or "application/pdf",
            **result,
        }

    if declares_pdf:
        return _base_result(
            final_url,
            content_type,
            "unsupported_content",
            error="The server declared a PDF but returned no PDF signature.",
        )

    # A PDF was requested but HTML or another format was returned.
    if requested_pdf:
        return _base_result(
            final_url,
            content_type,
            "unsupported_content",
            error="A PDF was requested, but the server returned non-PDF content.",
        )

    # Reject unsupported content types.
    is_html = (
        "text/html" in content_type
        or "application/xhtml+xml" in content_type
    )
    is_plain_text = "text/plain" in content_type

    if not is_html and not is_plain_text:
        return _base_result(
            final_url,
            content_type,
            "unsupported_content_type",
            error="The server returned an unsupported content type.",
        )

    # Handle plain-text sources.
    if is_plain_text:
        text = body.decode("utf-8", errors="replace")
        text = re.sub(r"\s+", " ", text).strip()

        if _looks_like_error_page(None, text):
            return _base_result(
                final_url,
                content_type,
                "unsupported_content",
                excerpt=text[:MAX_EXTRACTED_CHARS] or None,
                error="The server appears to have returned an error page.",
            )

        return _base_result(
            final_url,
            content_type,
            "extracted" if text else "empty_document",
            excerpt=text[:MAX_EXTRACTED_CHARS] or None,
        )

    # Parse HTML sources.
    soup = BeautifulSoup(body, "html.parser")

    published_at = _extract_publication_date(soup)

    title = (
        soup.title.get_text(" ", strip=True)
        if soup.title
        else None
    )

    # Remove non-content elements before extracting readable text.
    for element in soup(
        ["script", "style", "noscript", "nav", "footer", "header"]
    ):
        element.decompose()

    main = soup.find("main") or soup.find("article") or soup.body or soup

    text = re.sub(
        r"\s+",
        " ",
        main.get_text(" ", strip=True),
    ).strip()

    excerpt = text[:MAX_EXTRACTED_CHARS] or None

    if _looks_like_error_page(title, text):
        return {
            "final_url": final_url,
            "content_type": content_type,
            "title": title,
            "excerpt": excerpt,
            "published_at": published_at,
            "extraction_status": "unsupported_content",
            "error": "The server appears to have returned an HTML error page.",
        }

    return {
        "final_url": final_url,
        "content_type": content_type,
        "title": title,
        "excerpt": excerpt,
        "published_at": published_at,
        "extraction_status": "extracted" if text else "empty_document",
    }
