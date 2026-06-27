"""Application configuration loaded from environment variables."""

import os
from pathlib import Path

from dotenv import load_dotenv

# Always load backend/.env regardless of working directory
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env", override=True)

# Base paths
TEMPLATES_DIR = BASE_DIR / "templates"
UPLOADS_DIR = BASE_DIR / "uploads"
OUTPUTS_DIR = BASE_DIR / "outputs"

# Ensure runtime directories exist
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)

_PLACEHOLDER_KEYS = {
    "",
    "your_openai_api_key_here",
    "sk-your-key-here",
    "sk-your-actual-key-here",
}


def reload_env() -> None:
    """Reload backend/.env so key changes apply without a full server restart."""
    load_dotenv(BASE_DIR / ".env", override=True)


def get_openai_api_key() -> str:
    """Return the current OpenAI API key (always reads fresh from .env)."""
    reload_env()
    return os.getenv("OPENAI_API_KEY", "").strip()


def get_openai_model() -> str:
    """Return the configured OpenAI model name."""
    reload_env()
    return os.getenv("OPENAI_MODEL", "gpt-4o")


def is_openai_key_configured() -> bool:
    """Return True when a real (non-placeholder) API key is set."""
    key = get_openai_api_key()
    return key not in _PLACEHOLDER_KEYS and key.startswith("sk-")


# Backwards-compatible module-level reads (used at import time elsewhere)
OPENAI_API_KEY = get_openai_api_key()
OPENAI_MODEL = get_openai_model()

# Upload constraints
MAX_UPLOAD_SIZE_MB = int(os.getenv("MAX_UPLOAD_SIZE_MB", "20"))
MAX_UPLOAD_SIZE_BYTES = MAX_UPLOAD_SIZE_MB * 1024 * 1024
ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg"}
ALLOWED_MIME_TYPES = {
    "application/pdf",
    "image/png",
    "image/jpeg",
    "image/jpg",
}

# CORS
CORS_ORIGINS = os.getenv(
    "CORS_ORIGINS",
    "http://localhost:5173,http://127.0.0.1:5173",
).split(",")

# Extraction performance (balanced = faster, thorough = more scans, slower)
EXTRACTION_MODE = os.getenv("EXTRACTION_MODE", "balanced").strip().lower()
MAX_PDF_PAGES = int(os.getenv("MAX_PDF_PAGES", "3"))
GAP_FILL_ENABLED = os.getenv("GAP_FILL_ENABLED", "true").strip().lower() in ("1", "true", "yes")

# Excel template
EXCEL_TEMPLATE_PATH = TEMPLATES_DIR / "Solar_Template.xlsx"
