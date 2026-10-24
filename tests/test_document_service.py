
import io
from pathlib import Path

import pandas as pd
import pytest
import pymupdf
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from starlette.datastructures import Headers, UploadFile

from backend.app.models import Base, Case
from backend.app.models.document import Document
from backend.app.services import document_service


@pytest.fixture
def db_session():
    """Provide an isolated in-memory SQLite database."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    Base.metadata.create_all(engine)

    with Session(engine, expire_on_commit=False) as session:
        yield session

    engine.dispose()


@pytest.fixture
def upload_dir(tmp_path, monkeypatch):
    """Keep uploaded test files outside the real project data directory."""
    directory = tmp_path / "uploads"
    directory.mkdir()

    monkeypatch.setattr(
        document_service.settings,
        "UPLOAD_DIR",
        str(directory),
    )

    return directory


@pytest.fixture
def test_case(db_session):
    case = Case(
        business_name="Regression Test Business",
        loan_amount=100000,
        loan_purpose="Working capital",
    )
    db_session.add(case)
    db_session.commit()
    db_session.refresh(case)
    return case


def make_pdf(text="Financial statement test"):
    """Generate a small valid PDF in memory."""
    buffer = io.BytesIO()

    with pymupdf.open() as pdf:
        page = pdf.new_page()
        page.insert_text((72, 72), text)
        pdf.save(buffer)

    return buffer.getvalue()


def make_upload(
    filename,
    content,
    content_type="application/octet-stream",
):
    return UploadFile(
        filename=filename,
        file=io.BytesIO(content),
        headers=Headers({"content-type": content_type}),
    )


@pytest.mark.asyncio
async def test_successful_pdf_upload(
    db_session,
    test_case,
    upload_dir,
):
    content = make_pdf("Revenue 125000 Net Profit 25000")
    upload = make_upload("statement.pdf", content, "application/pdf")

    document = await document_service.upload_document(
        db_session,
        test_case.id,
        upload,
    )

    assert document.id
    assert document.case_id == test_case.id
    assert document.original_filename == "statement.pdf"
    assert document.document_type == "pdf"
    assert document.status == "processed"
    assert document.sha256
    assert len(document.sha256) == 64
    assert "Revenue 125000" in document.extracted_text

    stored_file = upload_dir / document.stored_filename
    assert stored_file.exists()
    assert stored_file.read_bytes() == content

    saved = db_session.get(Document, document.id)
    assert saved is not None
    assert saved.sha256 == document.sha256


@pytest.mark.asyncio
async def test_empty_file_is_rejected(
    db_session,
    test_case,
    upload_dir,
):
    upload = make_upload("empty.pdf", b"", "application/pdf")

    with pytest.raises(HTTPException) as exc:
        await document_service.upload_document(
            db_session,
            test_case.id,
            upload,
        )

    assert exc.value.status_code == 400
    assert "empty" in exc.value.detail.lower()
    assert list(upload_dir.iterdir()) == []


@pytest.mark.asyncio
async def test_invalid_pdf_is_rejected(
    db_session,
    test_case,
    upload_dir,
):
    upload = make_upload(
        "invalid.pdf",
        b"This is not a PDF",
        "application/pdf",
    )

    with pytest.raises(HTTPException) as exc:
        await document_service.upload_document(
            db_session,
            test_case.id,
            upload,
        )

    assert exc.value.status_code == 400
    assert "valid PDF" in exc.value.detail
    assert list(upload_dir.iterdir()) == []


@pytest.mark.asyncio
async def test_unsupported_extension_is_rejected(
    db_session,
    test_case,
    upload_dir,
):
    upload = make_upload("malware.exe", b"sample")

    with pytest.raises(HTTPException) as exc:
        await document_service.upload_document(
            db_session,
            test_case.id,
            upload,
        )

    assert exc.value.status_code == 415
    assert list(upload_dir.iterdir()) == []


@pytest.mark.asyncio
async def test_oversized_upload_is_rejected(
    db_session,
    test_case,
    upload_dir,
    monkeypatch,
):
    monkeypatch.setattr(document_service, "MAX_BYTES", 10)

    upload = make_upload(
        "large.pdf",
        b"%PDF-" + b"x" * 20,
        "application/pdf",
    )

    with pytest.raises(HTTPException) as exc:
        await document_service.upload_document(
            db_session,
            test_case.id,
            upload,
        )

    assert exc.value.status_code == 413
    assert list(upload_dir.iterdir()) == []


@pytest.mark.asyncio
async def test_missing_case_is_rejected(db_session, upload_dir):
    upload = make_upload("statement.pdf", make_pdf(), "application/pdf")

    with pytest.raises(HTTPException) as exc:
        await document_service.upload_document(
            db_session,
            "missing-case-id",
            upload,
        )

    assert exc.value.status_code == 404
    assert list(upload_dir.iterdir()) == []


def test_document_cannot_be_retrieved_from_another_case(
    db_session,
    test_case,
    upload_dir,
):
    second_case = Case(
        business_name="Another Business",
        loan_amount=50000,
        loan_purpose="Equipment",
    )
    db_session.add(second_case)
    db_session.commit()
    db_session.refresh(second_case)

    content = make_pdf()
    stored_name = "test-document.pdf"
    stored_path = upload_dir / stored_name
    stored_path.write_bytes(content)

    document = Document(
        case_id=test_case.id,
        original_filename="statement.pdf",
        stored_filename=stored_name,
        document_type="pdf",
        content_type="application/pdf",
        file_size=len(content),
        sha256="a" * 64,
        status="processed",
        extracted_text="Financial statement test",
    )
    db_session.add(document)
    db_session.commit()
    db_session.refresh(document)

    with pytest.raises(HTTPException) as exc:
        document_service.get_document(
            db_session,
            second_case.id,
            document.id,
        )

    assert exc.value.status_code == 404


def test_list_documents_only_returns_requested_case(
    db_session,
    test_case,
    upload_dir,
):
    document = Document(
        case_id=test_case.id,
        original_filename="statement.csv",
        stored_filename="test.csv",
        document_type="csv",
        content_type="text/csv",
        file_size=10,
        sha256="b" * 64,
        status="processed",
        extracted_text="Revenue 100",
    )
    db_session.add(document)
    db_session.commit()

    items, total = document_service.list_documents(
        db_session,
        test_case.id,
    )

    assert total == 1
    assert len(items) == 1
    assert items[0].case_id == test_case.id


@pytest.mark.asyncio
async def test_database_failure_cleans_up_uploaded_file(
    db_session,
    test_case,
    upload_dir,
    monkeypatch,
):
    def fail_commit():
        raise RuntimeError("Simulated database failure")

    # SQLAlchemyError is caught by the service's database-error handler.
    from sqlalchemy.exc import SQLAlchemyError

    def fail_database_commit():
        raise SQLAlchemyError("Simulated database failure")

    monkeypatch.setattr(db_session, "commit", fail_database_commit)

    upload = make_upload(
        "statement.pdf",
        make_pdf(),
        "application/pdf",
    )

    with pytest.raises(HTTPException) as exc:
        await document_service.upload_document(
            db_session,
            test_case.id,
            upload,
        )

    assert exc.value.status_code == 500
    assert list(upload_dir.iterdir()) == []


def test_csv_extraction():
    content = (
        b"Metric,Value\n"
        b"Revenue,125000\n"
        b"Net Profit,25000\n"
    )

    text = document_service.extract_content(".csv", content)

    assert "Revenue" in text
    assert "125000" in text
    assert "Net Profit" in text


def test_xlsx_extraction():
    buffer = io.BytesIO()

    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        pd.DataFrame(
            {
                "Metric": ["Revenue", "Net Profit"],
                "Value": [125000, 25000],
            }
        ).to_excel(writer, sheet_name="Financials", index=False)

    text = document_service.extract_content(".xlsx", buffer.getvalue())

    assert "Financials" in text
    assert "Revenue" in text
    assert "125000" in text
    assert "Net Profit" in text


def test_password_protected_pdf_is_rejected():
    buffer = io.BytesIO()

    with pymupdf.open() as pdf:
        page = pdf.new_page()
        page.insert_text((72, 72), "Confidential statement")
        pdf.save(
            buffer,
            encryption=pymupdf.PDF_ENCRYPT_AES_256,
            owner_pw="owner-secret",
            user_pw="user-secret",
        )

    with pytest.raises(ValueError, match="Password-protected"):
        document_service.extract_content(".pdf", buffer.getvalue())
