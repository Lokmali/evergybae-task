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
    MAX_UPLOAD_SIZE_BYTES,
    OUTPUTS_DIR,
    UPLOADS_DIR,
    is_openai_key_configured,
)
from services.bill_validator import CANONICAL_FIELDS
from services.ai_extractor import extract_bill_data, validate_extracted_data
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
    """Return image path(s) — convert all PDF pages (up to 3) for full bill capture."""
    if is_pdf(upload_path):
        return pdf_to_images(upload_path, max_pages=3)
    return [upload_path]


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
        extracted_data = validate_extracted_data(raw_data)

        # Persist extracted data for the generate step
        data_file = UPLOADS_DIR / f"{session_id}_data.json"
        with open(data_file, "w", encoding="utf-8") as f:
            json.dump(extracted_data, f, ensure_ascii=False, indent=2)

        return ExtractResponse(
            session_id=session_id,
            extracted_data=extracted_data,
            fields=EXTRACTABLE_FIELDS,
        )

    except HTTPException:
        raise
    except ValueError as exc:
        logger.warning("Extraction validation error: %s", exc)
        raise HTTPException(status_code=422, detail=str(exc)) from exc
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
        filename, output_path = fill_excel_template(sanitized)

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
