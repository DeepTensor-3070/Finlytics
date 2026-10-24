
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models.evidence import ExternalEvidence
from backend.app.services.evidence_service import create_evidence
from backend.app.services.evidence_validator import EvidenceInput
from backend.app.services.source_extractor import extract_source_page
from backend.app.services.tinyfish_client import search_external_evidence


GENERIC_TITLES = {"", "untitled", "unknown", "n/a"}


def normalize_url(url: str) -> str:
    """Normalize URLs for basic duplicate detection."""
    parts = urlsplit(url.strip())

    return urlunsplit(
        (
            parts.scheme.lower(),
            parts.netloc.lower(),
            parts.path.rstrip("/") or "/",
            parts.query,
            "",  # Ignore URL fragments.
        )
    )


async def collect_external_evidence(
    session: Session,
    case_id: str,
    query: str,
    expected_entity: str,
    *,
    max_results: int = 5,
) -> dict[str, Any]:
    """Search, enrich, validate, and persist external evidence candidates."""

    if not expected_entity.strip():
        raise ValueError("expected_entity cannot be empty.")

    candidates = await search_external_evidence(
        query,
        max_results=max_results,
    )

    # Load existing URLs for this case so repeat searches can skip them.
    existing_urls = session.scalars(
        select(ExternalEvidence.source_url).where(
            ExternalEvidence.case_id == case_id
        )
    ).all()

    existing_normalized_urls = {
        normalize_url(url) for url in existing_urls if url
    }

    summary: dict[str, Any] = {
        "case_id": case_id,
        "query": query,
        "searched": len(candidates),
        "saved": 0,
        "valid": 0,
        "needs_review": 0,
        "rejected": 0,
        "duplicates_skipped": 0,
        "items": [],
    }

    for candidate in candidates:
        source_url = candidate.get("source_url")

        if not source_url:
            summary["items"].append(
                {
                    "validation_status": "rejected",
                    "reason": "Search result has no source URL.",
                }
            )
            continue

        normalized_url = normalize_url(source_url)

        # Skip URLs already stored for this case.
        if normalized_url in existing_normalized_urls:
            summary["duplicates_skipped"] += 1
            summary["items"].append(
                {
                    "source_url": source_url,
                    "validation_status": "duplicate_skipped",
                    "extraction_status": "not_attempted",
                }
            )
            continue

        title = (candidate.get("claim") or "").strip()
        if title.casefold() in GENERIC_TITLES:
            title = ""

        source_name = candidate.get("source_name") or "Unknown source"
        excerpt = candidate.get("excerpt") or ""
        published_at = None
        extraction_status = "not_attempted"

        try:
            page = await extract_source_page(source_url)

            extraction_status = page.get(
                "extraction_status",
                "unknown",
            )

            page_title = (page.get("title") or "").strip()
            if not title and page_title:
                title = page_title

            page_excerpt = page.get("excerpt")
            if page_excerpt and page_excerpt.strip():
                excerpt = page_excerpt

            published_at = page.get("published_at")

            final_url = page.get("final_url")
            if final_url and final_url.startswith("https://"):
                source_url = final_url

        except Exception:
            # Keep the search candidate if fetching or extraction fails.
            extraction_status = "fetch_failed"

        # A redirect may resolve to a URL already stored for this case.
        normalized_url = normalize_url(source_url)

        if normalized_url in existing_normalized_urls:
            summary["duplicates_skipped"] += 1
            summary["items"].append(
                {
                    "source_url": source_url,
                    "validation_status": "duplicate_skipped",
                    "extraction_status": extraction_status,
                }
            )
            continue

        payload = EvidenceInput(
            claim=title,
            source_url=source_url,
            source_name=source_name,
            excerpt=excerpt,
            entity_name=expected_entity,
            expected_entity=expected_entity,
            published_at=published_at,
            retrieved_at=datetime.now(timezone.utc),
        )

        evidence, validation = create_evidence(
            session=session,
            case_id=case_id,
            payload=payload,
        )

        status = validation["status"]
        summary["saved"] += 1
        summary[status] += 1

        # Avoid duplicates within the current batch too.
        existing_normalized_urls.add(
            normalize_url(evidence.source_url)
        )

        summary["items"].append(
            {
                "id": evidence.id,
                "claim": evidence.claim,
                "source_name": evidence.source_name,
                "source_url": evidence.source_url,
                "validation_status": status,
                "validation_reasons": validation["reasons"],
                "extraction_status": extraction_status,
                "publication_date_found": published_at is not None,
            }
        )

    return summary
