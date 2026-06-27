"""API route handlers for bill upload and Excel generation."""

import json
import logging
import uuid
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from config import (
    ALLOWED_EXTENSIONS,
    ALLOWED_MIME_TYPES,
    MAX_PDF_PAGES,
    MAX_UPLOAD_SIZE_BYTES,
    OUTPUTS_DIR,
    UPLOADS_DIR,
    is_openai_key_configured,
)
from services.extractor import extract_bill_data, validate_extracted_data
from services.bill_validator import CANONICAL_FIELDS, strip_internal_metadata
from services.cell_mapping import EXTRACTABLE_FIELDS
from services.excel_writer import fill_excel_template
from services.pdf_converter import is_pdf, pdf_to_images

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["bill-processing"])


class ExtractResponse(BaseModel):
    """Response after AI extraction — includes editable preview data."""

    session_id: str
    extracted_data: dict
    fields: list[str]
    field_confidence: dict[str, int] = Field(default_factory=dict)
    solar_summary: dict = Field(default_factory=dict)


class GenerateRequest(BaseModel):
    """User-confirmed (optionally edited) data for Excel generation."""

    session_id: str
    data: dict = Field(default_factory=dict)


class GenerateResponse(BaseModel):
    """Response after Excel file is generated."""

    filename: str
    download_url: str
    message: str


def _validate_upload(file: UploadFile) -> None:
    """Validate file type and size before processing."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided.")

    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type '{ext}'. Allowed: PDF, PNG, JPG, JPEG.",
        )

    if file.content_type and file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid content type '{file.content_type}'.",
        )


async def _save_upload(file: UploadFile, session_id: str) -> Path:
    """Save uploaded file to disk with size validation."""
    ext = Path(file.filename).suffix.lower()
    dest = UPLOADS_DIR / f"{session_id}{ext}"

    size = 0
    try:
        with open(dest, "wb") as buffer:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_UPLOAD_SIZE_BYTES:
                    buffer.close()
                    dest.unlink(missing_ok=True)
                    raise HTTPException(
                        status_code=413,
                        detail=f"File too large. Maximum size is "
                        f"{MAX_UPLOAD_SIZE_BYTES // (1024 * 1024)} MB.",
                    )
                buffer.write(chunk)
    except HTTPException:
        raise
    except Exception as exc:
        dest.unlink(missing_ok=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to save upload: {exc}"
        ) from exc

    return dest


def _resolve_image_paths(upload_path: Path) -> list[Path]:
    """Return image path(s) — convert all PDF pages for full bill capture."""
    if is_pdf(upload_path):
        try:
            return pdf_to_images(upload_path, max_pages=MAX_PDF_PAGES)
        except Exception as exc:
            logger.warning("PDF conversion failed: %s", exc)
            raise HTTPException(
                status_code=422,
                detail="Unable to read PDF. Please upload a clearer file or try a JPG/PNG image.",
            ) from exc
    return [upload_path]


def _friendly_extraction_error(exc: Exception) -> str:
    """Map internal errors to user-facing messages."""
    msg = str(exc).lower()

    if "openai api key" in msg or "api key" in msg:
        return str(exc)
    if "pdf" in msg or "pymupdf" in msg or "fitz" in msg:
        return "Unable to read PDF. Please upload a clearer file or try a JPG/PNG image."
    if "image" in msg and ("quality" in msg or "empty" in msg or "invalid" in msg):
        return "Image quality is too low. Please upload a sharper, well-lit photo of the bill."
    if "empty response" in msg or "parse" in msg and "json" in msg:
        return "Could not read bill data. Please try again with a clearer upload."
    if "no valid image" in msg:
        return "Unable to process the uploaded file. Please try a PDF or image (PNG/JPG)."
    if "consumer" in msg and "not" in msg:
        return "Consumer Number not detected. Check the image and try again."
    if "bill amount" in msg or "amount missing" in msg:
        return "Bill Amount missing. Ensure the payment section of the bill is visible."

    return str(exc) if isinstance(exc, ValueError) else (
        "An unexpected error occurred during extraction. Please try again."
    )


@router.get("/health")
async def health_check():
    """Health check endpoint for monitoring."""
    return {
        "status": "ok",
        "service": "energybae-ai-solar-calculator",
        "openai_configured": is_openai_key_configured(),
    }


@router.get("/fields")
async def get_extractable_fields():
    """Return list of fields the AI extracts and maps to Excel."""
    # Include canonical extraction fields + Excel-mapped fields for preview UI
    fields = list(dict.fromkeys([*CANONICAL_FIELDS, *EXTRACTABLE_FIELDS]))
    return {"fields": fields}


@router.post("/extract", response_model=ExtractResponse)
async def extract_from_bill(file: UploadFile = File(...)):
    """
    Upload an electricity bill (PDF/image), extract data via OpenAI Vision.

    Returns extracted JSON for user preview and editing before Excel generation.
    """
    _validate_upload(file)
    session_id = str(uuid.uuid4())

    try:
        upload_path = await _save_upload(file, session_id)
        image_paths = _resolve_image_paths(upload_path)
        raw_data = extract_bill_data(image_paths)
        field_confidence = raw_data.pop("_field_confidence", {})
        solar_summary = raw_data.pop("_solar_summary", {})
        extracted_data = strip_internal_metadata(raw_data)

        # Persist extracted data for the generate step
        data_file = UPLOADS_DIR / f"{session_id}_data.json"
        with open(data_file, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "extracted_data": extracted_data,
                    "field_confidence": field_confidence,
                    "solar_summary": solar_summary,
                },
                f,
                ensure_ascii=False,
                indent=2,
            )

        return ExtractResponse(
            session_id=session_id,
            extracted_data=extracted_data,
            fields=EXTRACTABLE_FIELDS,
            field_confidence=field_confidence,
            solar_summary=solar_summary,
        )

    except HTTPException:
        raise
    except ValueError as exc:
        logger.warning("Extraction validation error: %s", exc)
        raise HTTPException(status_code=422, detail=_friendly_extraction_error(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Unexpected extraction error")
        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred during extraction. Please try again.",
        ) from exc


@router.post("/generate", response_model=GenerateResponse)
async def generate_excel(request: GenerateRequest):
    """
    Generate Excel from extracted (and optionally user-edited) bill data.
    """
    if not request.session_id:
        raise HTTPException(status_code=400, detail="session_id is required.")

    if not request.data:
        raise HTTPException(status_code=400, detail="No data provided for Excel generation.")

    try:
        sanitized = validate_extracted_data(request.data)
        excel_data = strip_internal_metadata(sanitized)
        filename, output_path = fill_excel_template(excel_data)

        return GenerateResponse(
            filename=filename,
            download_url=f"/api/download/{filename}",
            message="Solar calculation Excel generated successfully.",
        )

    except FileNotFoundError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Excel generation error")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate Excel: {exc}",
        ) from exc


@router.get("/download/{filename}")
async def download_excel(filename: str):
    """Download a generated Excel file."""
    # Prevent path traversal
    safe_name = Path(filename).name
    if not safe_name.startswith("Solar_Output_") or not safe_name.endswith(".xlsx"):
        raise HTTPException(status_code=400, detail="Invalid filename.")

    file_path = OUTPUTS_DIR / safe_name
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found or expired.")

    return FileResponse(
        path=file_path,
        filename=safe_name,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
