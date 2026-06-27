"""Convert PDF documents to high-resolution images for Vision API processing."""

import logging
from pathlib import Path

import fitz  # PyMuPDF
from PIL import Image

logger = logging.getLogger(__name__)

# Render at 3x zoom (~216 DPI) for small text on PDF bills
PDF_RENDER_MATRIX = fitz.Matrix(3.0, 3.0)

# Capture all pages including consumption graph annexures
DEFAULT_MAX_PDF_PAGES = 5


def pdf_to_images(
    pdf_path: Path,
    output_dir: Path | None = None,
    max_pages: int = DEFAULT_MAX_PDF_PAGES,
) -> list[Path]:
    """
    Convert PDF pages to PNG images for Vision API.

    Reads up to max_pages so 12-month consumption charts are included.

    Args:
        pdf_path: Source PDF file.
        output_dir: Directory for PNG files. Defaults to same folder as PDF.
        max_pages: Maximum pages to convert (cost/latency vs completeness).

    Returns:
        List of paths to generated PNG images, one per page.
    """
    if output_dir is None:
        output_dir = pdf_path.parent

    output_dir.mkdir(parents=True, exist_ok=True)
    images: list[Path] = []

    logger.info("Converting PDF to images: %s (max %d pages)", pdf_path.name, max_pages)

    try:
        with fitz.open(pdf_path) as doc:
            if doc.page_count == 0:
                raise ValueError("PDF file contains no pages.")

            page_count = min(doc.page_count, max_pages)
            for i in range(page_count):
                page = doc.load_page(i)
                out_path = output_dir / f"{pdf_path.stem}_page{i + 1}.png"
                pix = page.get_pixmap(matrix=PDF_RENDER_MATRIX, alpha=False)
                pix.save(str(out_path))

                with Image.open(out_path) as img:
                    img.convert("RGB").save(out_path, format="PNG", optimize=True)

                images.append(out_path)
                logger.debug("  Page %d → %s", i + 1, out_path.name)

    except fitz.FileDataError as exc:
        raise ValueError("Invalid or corrupted PDF file.") from exc
    except Exception as exc:
        raise ValueError(f"Failed to convert PDF: {exc}") from exc

    logger.info("PDF converted: %d page(s)", len(images))
    return images


def pdf_first_page_to_image(pdf_path: Path, output_path: Path | None = None) -> Path:
    """Convert only the first PDF page (backwards compatible)."""
    images = pdf_to_images(pdf_path, max_pages=1)
    if output_path and images:
        images[0].rename(output_path)
        return output_path
    return images[0]


def is_pdf(file_path: Path) -> bool:
    """Return True if the file extension indicates a PDF."""
    return file_path.suffix.lower() == ".pdf"
