# AAGCP-Vector PRO — Web Dashboard

A professional, interactive web dashboard to visualize PII detection and cleaning in action.

## What it shows

- 🔍 **Before/After Comparison** — side-by-side scan results showing PII reduction
- 📊 **PII Distribution Chart** — breakdown of detected PII by type
- ✓ **Cleaning Results** — re-embedded vectors, tokens minted, quarantined entries
- 💬 **Role-Based Queries** — see how analyst vs compliance officer views differ
- 🔒 **Privacy Breakdown** — demonstrates masked vs revealed data

## Quick Start

### 1. Install dependencies

```bash
pip install fastapi uvicorn numpy pyyaml
python -m pip install presidio-analyzer presidio-anonymizer sentence-transformers
python -m spacy download en_core_web_lg
```

### 2. Run the server

```bash
python app.py
```

You should see:

```
INFO:     Uvicorn running on http://0.0.0.0:8000
```

### 3. Open the dashboard

Open your browser and go to:

```
http://localhost:8000
```

### 4. Run the demo

Click the **"▶ Run Demo Pipeline"** button to execute the full pipeline:

- Generates 137 fake patient records with mixed PII
- Scans for PII (finds 456 instances across 26 types)
- Cleans vectors in place
- Re-scans to verify (now only 9 instances remain)
- Shows role-based query results

## What you'll see

### Dashboard Sections

1. **Detector Coverage** — shows 26 regex patterns + Presidio NER backend
2. **BEFORE Cleaning** — 137 vectors, 456 PII instances (the problem)
3. **AFTER Cleaning** — same vectors, 9 instances left (fixed)
4. **PII Chart** — pie chart of detected types (PERSON, MRN, EMAIL, SSN, etc.)
5. **Cleaning Stats** — how many vectors re-embedded, how many tokens created
6. **Query Results**:
   - BEFORE: Raw PII visible (Aadhaar, SSN, card numbers)
   - AFTER (Analyst): Same query, but masked/tokenized
   - AFTER (Compliance): Same data, but compliance officer can see full details

## Architecture

```
┌─ FastAPI Backend (app.py)
│  ├─ GET  /                    → Serve dashboard HTML
│  ├─ POST /api/run-demo        → Execute pipeline, return results
│  └─ GET  /api/status          → Get current pipeline status
│
├─ Static Files (static/)
│  ├─ style.css                 → Dashboard styling
│  └─ script.js                 → Frontend logic, API calls, Chart.js integration
│
└─ Templates (templates/)
   └─ dashboard.html            → Main UI
```

## For Business Users

This dashboard is designed to show stakeholders:

- ✓ How much PII is currently exposed in your vector DB
- ✓ What types of sensitive data exist (by jurisdiction)
- ✓ How the cleaning process works without breaking search
- ✓ How role-based access protects different user personas
- ✓ That retrieval quality is preserved after cleaning

## For Technical Demos

1. Start with the dashboard to show the problem (BEFORE)
2. Click "Run Demo" to show the solution in action
3. Highlight the "after" numbers to show PII reduction
4. Compare BEFORE/AFTER queries to demonstrate privacy
5. Show the role-based reveal to demonstrate governance

## Deployment

### Production setup

```bash
# Use gunicorn or your favorite ASGI server
pip install gunicorn
gunicorn -w 4 -k uvicorn.workers.UvicornWorker app:app
```

### Docker

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt && python -m spacy download en_core_web_lg
COPY . .
EXPOSE 8000
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
```

## Notes

- The demo always starts fresh (generates new random data each run)
- The vault is in-memory; data is not persisted
- For production, connect to real vector DBs (see SMOKE_TEST.md)
- Chart.js is loaded from CDN (requires internet)

## Troubleshooting

**Port 8000 already in use?**

```bash
python app.py --port 8001
```

**Missing Presidio?**

```bash
pip install presidio-analyzer presidio-anonymizer
python -m spacy download en_core_web_lg
```

**Static files not loading?**
Make sure you're running `app.py` from the project root directory.
