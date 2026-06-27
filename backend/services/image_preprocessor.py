"""
Image preprocessing for improved OCR / Vision API readability.

Balanced mode: 1 scan per PDF page, 1–2 scans for phone photos (~30–60s total).
Thorough mode: multiple variants + crops per page (~60–120s, higher accuracy).
"""

from __future__ import annotations

import logging
from pathlib import Path

from PIL import Image, ImageEnhance, ImageFilter, ImageOps

from config import EXTRACTION_MODE

logger = logging.getLogger(__name__)

THOROUGH = EXTRACTION_MODE == "thorough"

# Standard variant — balanced
STD_BRIGHTNESS = 1.05
STD_CONTRAST = 1.35
STD_SHARPNESS = 1.6

# High-detail variant
HD_BRIGHTNESS = 1.08
HD_CONTRAST = 1.55 if not THOROUGH else 1.65
HD_SHARPNESS = 1.8 if not THOROUGH else 2.0

STD_MIN_LONG_EDGE = 1600 if not THOROUGH else 1800
STD_MAX_LONG_EDGE = 2400 if not THOROUGH else 2800
HD_MIN_LONG_EDGE = 2000 if not THOROUGH else 2400
HD_MAX_LONG_EDGE = 2800 if not THOROUGH else 4096


def _auto_rotate(img: Image.Image) -> Image.Image:
    try:
        return ImageOps.exif_transpose(img)
    except Exception:
        return img


def _denoise(img: Image.Image) -> Image.Image:
    return img.filter(ImageFilter.MedianFilter(size=3))


def _scale_for_vision(img: Image.Image, min_edge: int, max_edge: int) -> Image.Image:
    w, h = img.size
    long_edge = max(w, h)
    if long_edge < min_edge:
        scale = min_edge / long_edge
        return img.resize((int(w * scale), int(h * scale)), Image.Resampling.LANCZOS)
    if long_edge > max_edge:
        scale = max_edge / long_edge
        return img.resize((int(w * scale), int(h * scale)), Image.Resampling.LANCZOS)
    return img


def _apply_variant(img: Image.Image, variant: str) -> Image.Image:
    if variant == "high_detail":
        img = ImageOps.autocontrast(img, cutoff=1)
        img = ImageEnhance.Brightness(img).enhance(HD_BRIGHTNESS)
        img = ImageEnhance.Contrast(img).enhance(HD_CONTRAST)
        img = ImageEnhance.Sharpness(img).enhance(HD_SHARPNESS)
        img = img.filter(ImageFilter.UnsharpMask(radius=1.2, percent=140, threshold=3))
    else:
        img = ImageEnhance.Brightness(img).enhance(STD_BRIGHTNESS)
        img = ImageEnhance.Contrast(img).enhance(STD_CONTRAST)
        img = ImageEnhance.Sharpness(img).enhance(STD_SHARPNESS)
    return img


def preprocess_image(
    image_path: Path,
    output_path: Path | None = None,
    variant: str = "standard",
) -> Path:
    suffix = "_hd" if variant == "high_detail" else "_std"
    if output_path is None:
        output_path = image_path.parent / f"{image_path.stem}{suffix}.png"

    min_edge = HD_MIN_LONG_EDGE if variant == "high_detail" else STD_MIN_LONG_EDGE
    max_edge = HD_MAX_LONG_EDGE if variant == "high_detail" else STD_MAX_LONG_EDGE

    with Image.open(image_path) as img:
        img = _auto_rotate(img)
        img = img.convert("RGB")
        img = _denoise(img)
        img = _scale_for_vision(img, min_edge, max_edge)
        img = _apply_variant(img, variant)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        img.save(output_path, format="PNG", optimize=False, compress_level=4)

    return output_path


def _make_detail_crops(source_path: Path, regions_only: str | None = None) -> list[tuple[Path, str]]:
    """Magnified crops for phone photos."""
    crops: list[tuple[Path, str]] = []
    with Image.open(source_path) as img:
        w, h = img.size
        all_regions = [
            (0, 0, w, int(h * 0.42), "header — consumer & tariff"),
            (0, int(h * 0.22), int(w * 0.58), int(h * 0.58), "tariff & load block"),
            (0, int(h * 0.38), w, int(h * 0.72), "middle — meter & readings"),
            (0, int(h * 0.65), w, h, "footer — charges & graph"),
        ]
        if regions_only == "footer":
            regions = [all_regions[3]]
        elif regions_only == "balanced":
            regions = [all_regions[1], all_regions[2], all_regions[3]]
        else:
            regions = all_regions

        for i, (x0, y0, x1, y1, desc) in enumerate(regions):
            if y1 - y0 < 80:
                continue
            crop = img.crop((x0, y0, x1, y1))
            cw, ch = crop.size
            target = 2000 if not THOROUGH else HD_MIN_LONG_EDGE
            if max(cw, ch) < target:
                scale = target / max(cw, ch)
                crop = crop.resize(
                    (int(cw * scale), int(ch * scale)), Image.Resampling.LANCZOS
                )
            crop = _apply_variant(crop, "high_detail")
            out = source_path.parent / f"{source_path.stem}_crop{i + 1}.png"
            crop.save(out, format="PNG", optimize=False)
            crops.append((out, desc))
    return crops


def preprocess_for_extraction(image_paths: list[Path]) -> list[tuple[Path, str]]:
    """
    Build image variants for Vision API.

    Balanced (default): 1 HD scan/page; photos get +1 footer crop.
    Thorough: 2 scans/page + 3 crops for photos.
    """
    is_photo = len(image_paths) == 1 and image_paths[0].suffix.lower() in {
        ".jpg", ".jpeg", ".png", ".webp"
    }

    result: list[tuple[Path, str]] = []

    for idx, path in enumerate(image_paths, start=1):
        page_label = f"Page {idx}" if len(image_paths) > 1 else "Bill"

        if THOROUGH:
            std = preprocess_image(path, variant="standard")
            result.append((std, f"{page_label} — full page"))
        hd = preprocess_image(path, variant="high_detail")
        result.append((hd, f"{page_label} — enhanced scan"))

        if is_photo:
            crop_mode = None if THOROUGH else "balanced"
            for crop_path, desc in _make_detail_crops(path, regions_only=crop_mode):
                result.append((crop_path, f"{page_label} — magnified: {desc}"))
        elif not THOROUGH:
            # PDF bills: add load + meter crops on first page only
            if idx == 1:
                for crop_path, desc in _make_detail_crops(path, regions_only="balanced"):
                    result.append((crop_path, f"{page_label} — magnified: {desc}"))

    logger.info(
        "Prepared %d vision image(s) from %d page(s) [mode=%s]",
        len(result),
        len(image_paths),
        EXTRACTION_MODE,
    )
    return result


def preprocess_images(image_paths: list[Path]) -> list[Path]:
    return [preprocess_image(p, variant="high_detail") for p in image_paths]
