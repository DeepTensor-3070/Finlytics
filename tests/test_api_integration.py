import io
from datetime import datetime, timezone

import pymupdf
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from backend.app.core.database import get_db
from backend.app.main import app
from backend.app.models import Base
from backend.app.services import document_service


@pytest.fixture
def api_client(tmp_path, monkeypatch):
    """Use an isolated in-memory database and temporary upload directory."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)

    upload_dir = tmp_path / "uploads"
    upload_dir.mkdir()

    monkeypatch.setattr(
        document_service.settings,
        "UPLOAD_DIR",
        str(upload_dir),
    )

    def override_get_db():
        with Session(engine, expire_on_commit=False) as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    try:
        # Do not enter the lifespan context: this test doesn't need
        # application startup to create directories in the real project.
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()


def make_financial_pdf():
    """Create a small, synthetic financial statement for testing."""
    text = """
    Integration Test Industries
    Financial Statement
    Reporting Period: 2025

    Revenue: INR 125000
    Net Profit: INR 25000
    Total Assets: INR 200000
    Total Liabilities: INR 80000
    Current Assets: INR 100000
    Current Liabilities: INR 50000
    """

    buffer = io.BytesIO()
    with pymupdf.open() as pdf:
        page = pdf.new_page()
        page.insert_textbox(
            (50, 50, 550, 750),
            text,
            fontsize=12,
        )
        pdf.save(buffer)

    return buffer.getvalue()


def test_case_to_risk_assessment_workflow(api_client):
    # 1. Create a case.
    case_response = api_client.post(
        "/api/v1/cases",
        json={
            "business_name": "Integration Test Industries",
            "business_type": "Manufacturing",
            "loan_amount": 100000,
            "loan_purpose": "Working capital",
            "currency": "INR",
        },
    )

    assert case_response.status_code == 201, case_response.text
    case = case_response.json()
    case_id = case["id"]

    assert case["business_name"] == "Integration Test Industries"

    # 2. Verify the case can be retrieved.
    get_case_response = api_client.get(f"/api/v1/cases/{case_id}")

    assert get_case_response.status_code == 200
    assert get_case_response.json()["id"] == case_id

    # 3. Upload a synthetic financial PDF.
    upload_response = api_client.post(
        f"/api/v1/cases/{case_id}/documents",
        files={
            "file": (
                "financial_statement.pdf",
                make_financial_pdf(),
                "application/pdf",
            )
        },
    )

    assert upload_response.status_code == 201, upload_response.text
    document = upload_response.json()

    assert document["case_id"] == case_id
    assert document["status"] == "processed"
    assert document["sha256"]

    # 4. Verify the document appears in the case document list.
    documents_response = api_client.get(
        f"/api/v1/cases/{case_id}/documents"
    )

    assert documents_response.status_code == 200
    assert documents_response.json()["total"] == 1

    # 5. Submit external evidence through the API.
    published_at = datetime.now(timezone.utc).isoformat()

    evidence_response = api_client.post(
        f"/api/v1/cases/{case_id}/evidence",
        json={
            "claim": (
                "Integration Test Industries reported financial "
                "information for its 2025 reporting period."
            ),
            "source_name": "Reserve Bank of India",
            "source_url": "https://www.rbi.org.in/",
            "excerpt": (
                "Integration Test Industries reported financial "
                "information for its 2025 reporting period."
            ),
            "entity_name": "Integration Test Industries",
            "expected_entity": "Integration Test Industries",
            "published_at": published_at,
        },
    )

    assert evidence_response.status_code == 201, evidence_response.text
    evidence_body = evidence_response.json()

    assert evidence_body["evidence"]["case_id"] == case_id
    assert evidence_body["evidence"]["validation_status"]
    assert "checks" in evidence_body["validation"]

    # 6. Verify the evidence is retrievable.
    evidence_list_response = api_client.get(
        f"/api/v1/cases/{case_id}/evidence"
    )

    assert evidence_list_response.status_code == 200
    assert evidence_list_response.json()["total"] == 1

    # 7. Generate the case-level risk assessment.
    assessment_response = api_client.post(
        f"/api/v1/cases/{case_id}/risk-assessment",
        params={
            "current_period": "2025",
        },
    )

    assert assessment_response.status_code == 200, assessment_response.text
    assessment = assessment_response.json()

    assert assessment["case_id"] == case_id
    assert assessment["documents_found"] == 1
    assert assessment["documents_analyzed"] == 1
    assert assessment["external_evidence_count"] == 1
    assert assessment["financial_fields"]
    assert "metrics" in assessment["financial_analysis"]
    assert "findings" in assessment["risk_assessment"]
    assert len(assessment["external_evidence"]) == 1

    # The validator evaluates source metadata and relevance; it does
    # not independently prove the underlying claim is factually true.
    assert assessment["external_evidence"][0]["validation_status"]


def test_risk_assessment_returns_404_for_missing_case(api_client):
    response = api_client.post(
        "/api/v1/cases/nonexistent-test-case/risk-assessment"
    )

    assert response.status_code == 404


def test_document_upload_rejects_unsupported_file(api_client):
    case_response = api_client.post(
        "/api/v1/cases",
        json={
            "business_name": "Upload Test Industries",
            "loan_amount": 50000,
            "loan_purpose": "Equipment purchase",
        },
    )

    assert case_response.status_code == 201, case_response.text
    case_id = case_response.json()["id"]

    response = api_client.post(
        f"/api/v1/cases/{case_id}/documents",
        files={
            "file": (
                "malware.exe",
                b"not a supported document",
                "application/octet-stream",
            )
        },
    )

    assert response.status_code == 415, response.text
