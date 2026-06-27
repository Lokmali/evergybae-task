"""
Energybae AI Solar Load Calculator — FastAPI Backend

Upload electricity bills, extract data via OpenAI Vision,
and generate completed solar calculation Excel files.
"""

import logging
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from config import CORS_ORIGINS, is_openai_key_configured
from routes.upload import router as upload_router

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle hooks."""
    if not is_openai_key_configured():
        logger.warning(
            "OPENAI_API_KEY is missing or still a placeholder. "
            "Edit backend/.env, save, and restart the server."
        )
    else:
        logger.info("Energybae AI backend started successfully.")
    yield
    logger.info("Energybae AI backend shutting down.")


app = FastAPI(
    title="Energybae AI Solar Load Calculator",
    description="Extract MSEDCL bill data and generate solar calculation Excel files.",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — allow React dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in CORS_ORIGINS],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(upload_router)


@app.get("/")
async def root():
    """Friendly landing page — backend is API-only; use the frontend to upload bills."""
    return {
        "service": "Energybae AI Solar Load Calculator API",
        "status": "running",
        "openai_configured": is_openai_key_configured(),
        "frontend": "http://localhost:5173",
        "docs": "http://localhost:8000/docs",
        "health": "http://localhost:8000/api/health",
        "message": "Open the frontend URL in your browser to upload electricity bills.",
    }


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Catch unhandled exceptions and return friendly JSON errors."""
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "An internal server error occurred. Please try again later."},
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
