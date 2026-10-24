from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models.case import Case
from backend.app.models.document import Document
from backend.app.models.evidence import ExternalEvidence
from backend.app.services.financial_analysis_service import analyze_financials
from backend.app.services.financial_extraction_service import (
    extract_financial_fields,
)
from backend.app.services.risk_assessment_service import assess_financial_risk


def build_case_risk_assessment(
    db: Session,
    case_id: str,
    *,
    current_period: str | None = None,
    previous_period: str | None = None,
) -> dict[str, Any]:
    """Build a preliminary risk assessment from stored case data."""

    case = db.get(Case, case_id)
    if case is None:
        raise ValueError("Case not found.")

    documents = list(
        db.scalars(
            select(Document)
            .where(Document.case_id == case_id)
            .order_by(Document.created_at.asc())
        ).all()
    )

    evidence_records = list(
        db.scalars(
            select(ExternalEvidence)
            .where(ExternalEvidence.case_id == case_id)
            .order_by(ExternalEvidence.created_at.desc())
        ).all()
    )

    # Extract from processed documents with non-empty extracted text.
    usable_documents = [
        document
        for document in documents
        if document.status == "processed"
        and document.extracted_text
        and document.extracted_text.strip()
    ]

    document_results = []
    combined_fields: dict[str, Any] = {}

    for document in usable_documents:
        extracted = extract_financial_fields(document.extracted_text)

        document_results.append(
            {
                "document_id": document.id,
                "filename": document.original_filename,
                "sha256": document.sha256,
                "extraction": extracted,
            }
        )

        # Do not silently merge values from separate documents. The
        # combined extraction can create false ambiguity or mix periods.
        # Multiple documents are returned individually for review.
        for field_name, field_result in extracted.items():
            existing = combined_fields.get(field_name)

            if existing is None:
                combined_fields[field_name] = field_result
            else:
                combined_fields[field_name] = {
                    "value": None,
                    "currency": None,
                    "status": "ambiguous",
                    "candidates": [
                        *existing.get("candidates", []),
                        *field_result.get("candidates", []),
                    ],
                    "reason": (
                        "This field appears in multiple documents. "
                        "Review document-level values before selecting "
                        "a source."
                    ),
                }

    if not usable_documents:
        financial_fields = extract_financial_fields("")
        financial_analysis = analyze_financials(
            financial_fields,
            current_period=current_period,
            previous_period=previous_period,
        )
    else:
        financial_fields = combined_fields
        financial_analysis = analyze_financials(
            financial_fields,
            current_period=current_period,
            previous_period=previous_period,
        )

    evidence_data = [
        {
            "id": item.id,
            "claim": item.claim,
            "source_name": item.source_name,
            "source_url": item.source_url,
            "validation_status": item.validation_status,
            "validation_reason": item.validation_reason,
            "excerpt": item.excerpt,
            "published_at": (
                item.published_at.isoformat()
                if item.published_at
                else None
            ),
            "retrieved_at": (
                item.retrieved_at.isoformat()
                if item.retrieved_at
                else None
            ),
        }
        for item in evidence_records
    ]

    assessment = assess_financial_risk(
        financial_analysis,
        external_evidence=evidence_data,
    )

    return {
        "case_id": case.id,
        "business_name": case.business_name,
        "assessment_type": "preliminary_financial_risk",
        "documents_found": len(documents),
        "documents_analyzed": len(usable_documents),
        "documents": document_results,
        "financial_fields": financial_fields,
        "financial_analysis": financial_analysis,
        "risk_assessment": assessment,
        "external_evidence_count": len(evidence_records),
        "external_evidence": evidence_data,
        "limitations": [
            "This is a preliminary analytical aid, not a lending decision.",
            "Extracted figures must be checked against the original documents.",
            "Values appearing in multiple documents require source selection.",
            "Source validation does not prove that an external claim is true.",
        ],
    }
