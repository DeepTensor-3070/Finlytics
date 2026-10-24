
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from backend.app.services.evidence_collection_service import (
    collect_external_evidence,
)


@pytest.mark.asyncio
async def test_existing_source_is_skipped():
    existing_url = "https://example.com/report"

    class FakeSession:
        def scalars(self, statement):
            class Result:
                def all(self):
                    return [existing_url]

            return Result()

    with patch(
        "backend.app.services.evidence_collection_service.search_external_evidence",
        new_callable=AsyncMock,
    ) as mock_search:
        mock_search.return_value = [
            {
                "source_url": existing_url,
                "source_name": "Example",
                "claim": "Financial report",
                "excerpt": "Financial report excerpt",
            }
        ]

        result = await collect_external_evidence(
            session=FakeSession(),
            case_id="case-123",
            query="financial report",
            expected_entity="Example Company",
        )

    assert result["searched"] == 1
    assert result["saved"] == 0
    assert result["duplicates_skipped"] == 1
    assert result["items"][0]["validation_status"] == "duplicate_skipped"


@pytest.mark.asyncio
async def test_duplicate_urls_in_same_batch_are_saved_once():
    duplicate_url = "https://crisil.com/ratings/report"

    class FakeScalarResult:
        def all(self):
            return []

    class FakeSession:
        def scalars(self, statement):
            return FakeScalarResult()

    candidates = [
        {
            "source_url": duplicate_url,
            "source_name": "CRISIL",
            "claim": "Example Company credit rating",
            "excerpt": "Example Company credit rating report.",
        },
        {
            "source_url": duplicate_url,
            "source_name": "CRISIL",
            "claim": "Example Company credit rating",
            "excerpt": "Example Company credit rating report.",
        },
    ]

    fake_evidence = type(
        "FakeEvidence",
        (),
        {
            "id": "evidence-1",
            "claim": "Example Company credit rating",
            "source_name": "CRISIL",
            "source_url": duplicate_url,
        },
    )()

    fake_validation = {
        "status": "needs_review",
        "reasons": ["Publication date is unavailable."],
    }

    with (
        patch(
            "backend.app.services.evidence_collection_service.search_external_evidence",
            new_callable=AsyncMock,
            return_value=candidates,
        ),
        patch(
            "backend.app.services.evidence_collection_service.extract_source_page",
            new_callable=AsyncMock,
            return_value={
                "final_url": duplicate_url,
                "title": "Example Company credit rating",
                "excerpt": "Example Company credit rating report.",
                "published_at": datetime.now(timezone.utc),
                "extraction_status": "extracted",
            },
        ),
        patch(
            "backend.app.services.evidence_collection_service.create_evidence",
            return_value=(fake_evidence, fake_validation),
        ) as mock_create,
    ):
        result = await collect_external_evidence(
            session=FakeSession(),
            case_id="case-123",
            query="Example Company credit rating",
            expected_entity="Example Company",
        )

    assert result["searched"] == 2
    assert result["saved"] == 1
    assert result["duplicates_skipped"] == 1
    assert mock_create.call_count == 1


@pytest.mark.asyncio
async def test_new_source_is_saved():
    source_url = "https://crisil.com/ratings/new-report"

    class FakeScalarResult:
        def all(self):
            return []

    class FakeSession:
        def scalars(self, statement):
            return FakeScalarResult()

    candidates = [
        {
            "source_url": source_url,
            "source_name": "CRISIL",
            "claim": "Example Company credit rating",
            "excerpt": "Example Company credit rating report.",
        }
    ]

    fake_evidence = type(
        "FakeEvidence",
        (),
        {
            "id": "evidence-new",
            "claim": "Example Company credit rating",
            "source_name": "CRISIL",
            "source_url": source_url,
        },
    )()

    fake_validation = {
        "status": "needs_review",
        "reasons": ["Publication date is unavailable."],
    }

    with (
        patch(
            "backend.app.services.evidence_collection_service.search_external_evidence",
            new_callable=AsyncMock,
            return_value=candidates,
        ),
        patch(
            "backend.app.services.evidence_collection_service.extract_source_page",
            new_callable=AsyncMock,
            return_value={
                "final_url": source_url,
                "title": "Example Company credit rating",
                "excerpt": "Example Company credit rating report.",
                "published_at": None,
                "extraction_status": "extracted",
            },
        ),
        patch(
            "backend.app.services.evidence_collection_service.create_evidence",
            return_value=(fake_evidence, fake_validation),
        ) as mock_create,
    ):
        result = await collect_external_evidence(
            session=FakeSession(),
            case_id="case-123",
            query="Example Company credit rating",
            expected_entity="Example Company",
        )

    assert result["searched"] == 1
    assert result["saved"] == 1
    assert result["needs_review"] == 1
    assert result["duplicates_skipped"] == 0
    assert mock_create.call_count == 1
