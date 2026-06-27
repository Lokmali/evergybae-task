FROM python:3.12-slim-bookworm

WORKDIR /app

# Build tools for native extensions (PyMuPDF, Pillow)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Railway injects PORT at runtime
CMD uvicorn app:app --host 0.0.0.0 --port ${PORT:-8000}
