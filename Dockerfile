# Build FastAPI backend from monorepo root (Railway: leave Root Directory empty)
FROM python:3.12-slim-bookworm

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ .

CMD uvicorn app:app --host 0.0.0.0 --port ${PORT:-8000}
