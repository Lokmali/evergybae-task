# Energybae AI Solar Load Calculator

A production-ready MVP that lets users upload Maharashtra MSEDCL electricity bills (PDF or image), extracts bill data using **OpenAI Vision**, and automatically fills a solar load calculation Excel template — **without modifying formulas**.

![Tech Stack](https://img.shields.io/badge/React-Vite-61DAFB?style=flat-square)
![Tech Stack](https://img.shields.io/badge/FastAPI-Python-009688?style=flat-square)
![Tech Stack](https://img.shields.io/badge/AI-OpenAI_Vision-412991?style=flat-square)

---

## Features

- **Drag & drop upload** — PDF, PNG, JPG, JPEG (max 20 MB)
- **PDF handling** — First page converted to high-resolution image via PyMuPDF
- **AI extraction** — OpenAI GPT-4o Vision reads MSEDCL bills and returns structured JSON
- **Editable preview** — Review and correct extracted values before generating Excel
- **Formula-safe Excel** — Only input cells are populated; calculation formulas remain intact
- **Modern UI** — Tailwind CSS, progress indicators, toast notifications, responsive design
- **Secure** — API key stored server-side only; file type and size validation

---

## Folder Structure

```
energybae-ai/
├── README.md
├── .gitignore
│
├── backend/
│   ├── app.py                  # FastAPI entry point
│   ├── config.py               # Environment & path configuration
│   ├── requirements.txt
│   ├── .env.example
│   ├── routes/
│   │   └── upload.py           # /api/extract, /api/generate, /api/download
│   ├── services/
│   │   ├── ai_extractor.py     # OpenAI Vision extraction
│   │   ├── excel_writer.py     # Template population (openpyxl)
│   │   ├── pdf_converter.py    # PDF → PNG conversion
│   │   └── cell_mapping.py     # Field → cell mapping (easy to edit)
│   ├── scripts/
│   │   └── create_template.py  # Generates Solar_Template.xlsx
│   ├── templates/
│   │   └── Solar_Template.xlsx
│   ├── uploads/                # Temporary uploaded files
│   └── outputs/                # Generated Excel files
│
└── frontend/
    ├── package.json
    ├── vite.config.js
    ├── tailwind.config.js
    ├── index.html
    └── src/
        ├── App.jsx
        ├── main.jsx
        ├── index.css
        ├── components/
        │   ├── FileUpload.jsx
        │   ├── LoadingOverlay.jsx
        │   ├── DataPreview.jsx
        │   └── Toast.jsx
        └── services/
            └── api.js
```

---

## Prerequisites

- **Python 3.10+**
- **Node.js 18+** and npm
- **OpenAI API key** with access to a vision-capable model (`gpt-4o` recommended)

---

## Backend Setup

### 1. Create virtual environment (recommended)

```bash
cd backend
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure environment

```bash
copy .env.example .env   # Windows
# cp .env.example .env   # macOS / Linux
```

Edit `.env` and set your OpenAI API key:

```env
OPENAI_API_KEY=sk-your-key-here
OPENAI_MODEL=gpt-4o
MAX_UPLOAD_SIZE_MB=20
CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
```

### 4. Generate Excel template (if missing)

```bash
python scripts/create_template.py
```

### 5. Run the backend

```bash
uvicorn app:app --reload --host 0.0.0.0 --port 8000
```

API docs: [http://localhost:8000/docs](http://localhost:8000/docs)

---

## Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

Open [http://localhost:5173](http://localhost:5173)

The Vite dev server proxies `/api` requests to `http://localhost:8000`.

### Production build

```bash
npm run build
npm run preview
```

For production, set `VITE_API_URL` to your backend URL:

```env
VITE_API_URL=https://api.yourdomain.com
```

---

## Application Flow

1. **Upload** — User drops or selects a bill (PDF/image)
2. **Convert** — PDF first page → high-res PNG (PyMuPDF)
3. **Extract** — Image sent to OpenAI Vision → JSON fields
4. **Preview** — User reviews/edits extracted data
5. **Generate** — Backend fills `Solar_Template.xlsx` input cells
6. **Download** — User downloads `Solar_Output_<timestamp>.xlsx`

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/health` | Health check |
| GET | `/api/fields` | List extractable field names |
| POST | `/api/extract` | Upload bill, return extracted JSON |
| POST | `/api/generate` | Generate Excel from confirmed data |
| GET | `/api/download/{filename}` | Download generated Excel |

---

## Customizing Excel Mapping

Edit `backend/services/cell_mapping.py` to change which fields map to which cells:

```python
CELL_MAPPING = {
    "consumer_name": "B4",
    "units_consumed": "D12",
    "bill_amount": "D14",
    # ...
}
```

Formulas in the template (e.g. solar capacity calculations in `B22`–`B26`) are never overwritten.

---

## Error Handling

The application handles:

- Invalid file types and oversized uploads (> 20 MB)
- Missing or invalid OpenAI API key
- OpenAI API failures and timeouts
- Missing Excel template
- JSON parsing errors from AI responses
- Network errors (frontend)

All errors return user-friendly messages via toast notifications.

---

## Security Notes

- OpenAI API key is **never** exposed to the frontend
- Upload file types are validated by extension and MIME type
- Download filenames are sanitized to prevent path traversal
- CORS is restricted to configured frontend origins

---

## Future Improvements

- [ ] Multi-page PDF support (merge all pages)
- [ ] User authentication and bill history
- [ ] Support for other state electricity boards (besides MSEDCL)
- [ ] Batch processing for multiple bills
- [ ] Custom Excel template upload
- [ ] Docker Compose for one-command deployment
- [ ] Automated cleanup of old uploads/outputs
- [ ] Webhook notifications when processing completes
- [ ] Confidence scores per extracted field
- [ ] Hindi/Marathi bill OCR optimization

---

## License

MIT — use freely for commercial and personal projects.

---

Built with ❤️ by Energybae AI
