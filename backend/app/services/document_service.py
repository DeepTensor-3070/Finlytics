
import hashlib
import io
import logging
import re
import uuid
import zipfile
from pathlib import Path

import pandas as pd
import pymupdf
from fastapi import HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from backend.app.core.config import get_settings
from backend.app.models.case import Case
from backend.app.models.document import Document

logger = logging.getLogger(__name__)

settings = get_settings()

ALLOWED_EXTENSIONS = {".pdf", ".csv", ".xlsx"}
MAX_BYTES = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
CHUNK_SIZE = 1024 * 1024
MAX_PDF_PAGES = 500
MAX_WORKSHEETS = 20
MAX_ROWS_PER_SHEET = 1000


def safe_display_name(filename: str) -> str:
    """Sanitize a client-supplied filename for display only."""
    name = Path(filename).name.replace("\x00", "")
    name = re.sub(r"[^A-Za-z0-9._() -]", "_", name)
    return name[:255] or "uploaded_document"


def validate_content(extension: str, content: bytes) -> None:
    """Validate basic file signatures and structure."""
    if not content:
        raise HTTPException(status_code=400, detail="The uploaded file is empty.")

    if extension == ".pdf":
        if not content.startswith(b"%PDF-"):
            raise HTTPException(
                status_code=400,
                detail="The file does not appear to be a valid PDF.",
            )

    elif extension == ".xlsx":
        if not zipfile.is_zipfile(io.BytesIO(content)):
            raise HTTPException(
                status_code=400,
                detail="The file does not appear to be a valid XLSX.",
            )

        try:
            with zipfile.ZipFile(io.BytesIO(content)) as archive:
                names = set(archive.namelist())

                if "[Content_Types].xml" not in names:
                    raise HTTPException(
                        status_code=400,
                        detail="Invalid XLSX structure.",
                    )

                if "xl/workbook.xml" not in names:
                    raise HTTPException(
                        status_code=400,
                        detail="Invalid XLSX workbook.",
                    )

                if not any(
                    name.startswith("xl/worksheets/")
                    and name.endswith(".xml")
                    for name in names
                ):
                    raise HTTPException(
                        status_code=400,
                        detail="XLSX contains no worksheets.",
                    )

        except zipfile.BadZipFile:
            raise HTTPException(
                status_code=400,
                detail="Invalid XLSX archive.",
            ) from None

    elif extension == ".csv":
        try:
            content.decode("utf-8-sig")
        except UnicodeDecodeError:
            raise HTTPException(
                status_code=400,
                detail="CSV must use UTF-8 encoding. Convert the file and retry.",
            ) from None


def extract_content(extension: str, content: bytes) -> str:
    """Extract readable text from supported document formats."""
    if extension == ".pdf":
        try:
            with pymupdf.open(stream=content, filetype="pdf") as pdf:
                if pdf.needs_pass:
                    raise ValueError(
                        "Password-protected PDFs are not supported yet."
                    )

                if pdf.page_count > MAX_PDF_PAGES:
                    raise ValueError(
                        f"PDF exceeds the {MAX_PDF_PAGES}-page limit."
                    )

                pages = []

                for page_number, page in enumerate(pdf, start=1):
                    text = page.get_text()

                    if text.strip():
                        pages.append(
                            f"--- Page {page_number} ---\n{text}"
                        )

                # An image-only PDF needs OCR, which is not implemented here.
                return "\n\n".join(pages)

        except ValueError:
            raise
        except Exception as exc:
            raise ValueError("Unable to read the PDF document.") from exc

    if extension == ".csv":
        try:
            frame = pd.read_csv(
                io.BytesIO(content),
                nrows=MAX_ROWS_PER_SHEET,
                encoding="utf-8-sig",
            )
            return frame.to_string(index=False, max_rows=MAX_ROWS_PER_SHEET)
        except Exception as exc:
            raise ValueError("Unable to parse the CSV document.") from exc

    if extension == ".xlsx":
        output = []

        try:
            with pd.ExcelFile(
                io.BytesIO(content),
                engine="openpyxl",
            ) as workbook:
                for sheet_name in workbook.sheet_names[:MAX_WORKSHEETS]:
                    frame = pd.read_excel(
                        workbook,
                        sheet_name=sheet_name,
                        nrows=MAX_ROWS_PER_SHEET,
                    )

                    output.append(
                        f"--- Sheet: {sheet_name} ---\n"
                        f"{frame.to_string(index=False, max_rows=MAX_ROWS_PER_SHEET)}"
                    )

            return "\n\n".join(output)

        except Exception as exc:
            raise ValueError("Unable to parse the XLSX document.") from exc

    raise ValueError("Unsupported document format.")


async def upload_document(
    db: Session,
    case_id: str,
    upload: UploadFile,
) -> Document:
    """Validate, extract, store, and register an uploaded document."""
    destination: Path | None = None
    committed = False

    try:
        # 1. Verify the parent case exists.
        case = db.get(Case, case_id)

        if case is None:
            raise HTTPException(
                status_code=404,
                detail="Case not found.",
            )

        # 2. Validate the extension.
        original_name = safe_display_name(upload.filename or "")
        extension = Path(original_name).suffix.lower()

        if extension not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=415,
                detail="Unsupported file type. Upload PDF, CSV, or XLSX.",
            )

        # 3. Read in bounded chunks.
        chunks: list[bytes] = []
        total_bytes = 0

        while True:
            chunk = await upload.read(CHUNK_SIZE)

            if not chunk:
                break

            total_bytes += len(chunk)

            if total_bytes > MAX_BYTES:
                raise HTTPException(
                    status_code=413,
                    detail=(
                        f"File exceeds the "
                        f"{settings.MAX_UPLOAD_SIZE_MB} MB limit."
                    ),
                )

            chunks.append(chunk)

        content = b"".join(chunks)

        # 4. Validate the file structure.
        validate_content(extension, content)

        # 5. Calculate a content checksum.
        sha256 = hashlib.sha256(content).hexdigest()

        # 6. Extract content before writing persistent data.
        try:
            extracted_text = extract_content(extension, content)
        except ValueError as exc:
            logger.warning(
                "Document extraction rejected: case_id=%s, "
                "filename=%s, reason=%s",
                case_id,
                original_name,
                str(exc),
            )
            raise HTTPException(
                status_code=422,
                detail=str(exc),
            ) from exc

        # 7. Store using a generated name, never the client filename.
        upload_dir = settings.upload_path
        upload_dir.mkdir(parents=True, exist_ok=True)

        stored_name = f"{uuid.uuid4().hex}{extension}"
        destination = upload_dir / stored_name

        document = Document(
            case_id=case_id,
            original_filename=original_name,
            stored_filename=stored_name,
            document_type=extension.removeprefix("."),
            content_type=(
                upload.content_type or "application/octet-stream"
            ),
            file_size=total_bytes,
            sha256=sha256,
            status="processed",
            extracted_text=extracted_text,
            extraction_error=None,
        )

        # Exclusive creation avoids accidentally overwriting an existing file.
        with destination.open("xb") as stored_file:
            stored_file.write(content)

        # 8. Persist document metadata.
        db.add(document)
        db.commit()
        committed = True

        db.refresh(document)

        logger.info(
            "Document processed: document_id=%s, case_id=%s, "
            "format=%s, bytes=%s",
            document.id,
            case_id,
            extension,
            total_bytes,
        )

        return document

    except HTTPException:
        if not committed:
            db.rollback()

        if destination is not None and not committed:
            try:
                destination.unlink(missing_ok=True)
            except OSError:
                logger.exception(
                    "Could not clean up failed upload: case_id=%s",
                    case_id,
                )

        raise

    except SQLAlchemyError:
        if not committed:
            db.rollback()

        if destination is not None and not committed:
            try:
                destination.unlink(missing_ok=True)
            except OSError:
                logger.exception(
                    "Could not clean up upload after database failure: "
                    "case_id=%s",
                    case_id,
                )

        logger.exception(
            "Database error while saving document: case_id=%s",
            case_id,
        )

        raise HTTPException(
            status_code=500,
            detail="Could not save document metadata. Check server logs.",
        ) from None

    except Exception:
        if not committed:
            db.rollback()

        if destination is not None and not committed:
            try:
                destination.unlink(missing_ok=True)
            except OSError:
                logger.exception(
                    "Could not clean up failed upload: case_id=%s",
                    case_id,
                )

        logger.exception(
            "Unexpected document processing failure: case_id=%s",
            case_id,
        )

        raise HTTPException(
            status_code=500,
            detail="Document processing failed. Check server logs.",
        ) from None

    finally:
        await upload.close()


def list_documents(
    db: Session,
    case_id: str,
) -> tuple[list[Document], int]:
    """Return all document metadata associated with a case."""
    if db.get(Case, case_id) is None:
        raise HTTPException(
            status_code=404,
            detail="Case not found.",
        )

    items = list(
        db.scalars(
            select(Document)
            .where(Document.case_id == case_id)
            .order_by(Document.created_at.desc())
        ).all()
    )

    return items, len(items)


def get_document(
    db: Session,
    case_id: str,
    document_id: str,
) -> Document:
    """Retrieve a document only when it belongs to the specified case."""
    document = db.scalar(
        select(Document).where(
            Document.id == document_id,
            Document.case_id == case_id,
        )
    )

    if document is None:
        raise HTTPException(
            status_code=404,
            detail="Document not found for this case.",
        )

    return document
