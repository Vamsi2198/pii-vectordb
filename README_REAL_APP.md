# AAGCP + Pinecone Real Application

A **production-ready** PII detection, scanning, and cleaning system that integrates:

- **AAGCP Core Library** — the engine for detecting, scanning, and cleaning PII
- **Pinecone** — scalable vector store for real documents
- **SentenceTransformer** — real embeddings (384-dimensional)
- **Presidio** (optional) — advanced NER for PII types beyond regex

This is **not a demo**. It works with real data and produces real audit trails via `PseudonymVault`.

## Quick Start

### 1. Prerequisites

```bash
# Already installed in myenv:
pip install pinecone sentence-transformers fastapi uvicorn

# Optional but recommended (advanced PII detection):
pip install presidio-analyzer presidio-anonymizer
python -m spacy download en_core_web_lg
```

### 2. Set Environment

Your `.env` already has `PINECONE_API_KEY`. The app will auto-detect and use the `hybrid-search-langchain-pinecone` index (384D, matches your embeddings).

```bash
cd "C:\Users\HP\OneDrive\Documents\dinesh sir\aagcp_pro"
```

### 3. Run the App

```bash
python app_aagcp_pinecone.py
# or with uvicorn directly:
# uvicorn app_aagcp_pinecone:app --host 0.0.0.0 --port 8001
```

You should see:

```
[INIT] Connecting to Pinecone index: hybrid-search-langchain-pinecone
[INIT] Pinecone connector ready. Current vector count: N
[INIT] Loading SentenceTransformer embedder (all-MiniLM-L6-v2)...
[INIT] Embedder dimension: 384
[INIT] Initializing PII Detector...
[INIT] PII backend: {...}
[INIT] PseudonymVault initialized
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8001
```

### 4. Open Dashboard

Visit: **http://localhost:8001**

You'll see a live dashboard with:

- **Index Status** — current vector count
- **Ingest Documents** — upload real files (txt, pdf, docx)
- **Scan for PII** — scan entire index, get detection report
- **Clean Vectors** — mask PII and re-embed, producing audit trail
- **Query** — semantic search with masked results

---

## What This App Does (Real Workflow)

### Step 1: Ingest Real Documents

Upload a text, PDF, or Word file. The app:

1. Chunks the document (500 chars per chunk, no overlap)
2. Embeds each chunk (384-dim SentenceTransformer)
3. Stores in Pinecone with metadata (`doc_id`, `filename`, `chunk_idx`)
4. Each chunk keeps `source_text` in metadata (required for cleaning)

### Step 2: Scan for PII

Click "Scan Entire Index" to:

1. Stream **all vectors** from Pinecone (no cap)
2. Run PIIDetector on each chunk's `source_text`
3. Detect patterns: emails, SSN, phone, credit cards, names (if Presidio installed), etc.
4. Generate a detailed report with:
   - Total PII detections
   - Unique entity types
   - High-confidence findings
   - Vectors that can be cleaned vs. quarantined

### Step 3: Clean & Re-embed

Click "Clean & Re-embed" to:

1. Mask all detected PII (e.g., "John Smith" → `[PERSON]`)
2. Re-embed the masked chunks
3. Upsert back to Pinecone (replace poisoned vectors)
4. Create audit trail in `PseudonymVault` mapping real values → tokens
5. Report: how many cleaned, how many quarantined (no source text)

### Step 4: Query with Cleaned Data

Search for information. Results now have masked PII:

- Instead of: `"Contact John Smith at john@example.com"`
- You get: `"Contact [PERSON] at [EMAIL]"`

Re-hydrate specific results with `PseudonymVault.rectify()` if authorized.

---

## Architecture

```
┌─ app_aagcp_pinecone.py (FastAPI server)
│
├─ aagcp/detect/detector.py (PIIDetector)
│  └─ Regex + optional Presidio for PII patterns
│
├─ aagcp/embed/embedders.py (SentenceTransformerEmbedder)
│  └─ all-MiniLM-L6-v2 model (384D vectors)
│
├─ aagcp/store/connectors.py (PineconeConnector)
│  └─ Pinecone index (hybrid-search-langchain-pinecone)
│
├─ aagcp/scan/scanner.py (Scanner)
│  └─ Full-index scanning for PII
│
├─ aagcp/migrate/migrator.py (Migrator)
│  └─ Cleaning + re-embedding
│
└─ aagcp/vault.py (PseudonymVault)
   └─ Secure audit trail & re-hydration
```

---

## API Endpoints

| Endpoint  | Method | Description              |
| --------- | ------ | ------------------------ |
| `/`       | GET    | Dashboard UI             |
| `/status` | GET    | Index status JSON        |
| `/ingest` | POST   | Upload & ingest document |
| `/scan`   | GET    | Scan index for PII       |
| `/clean`  | POST   | Clean poisoned vectors   |
| `/query`  | POST   | Semantic search          |

---

## Example: Ingest a Document

**Upload via UI:**

1. Open http://localhost:8001
2. Select a `.txt` file (e.g., "sample.txt" with PII like "Contact John at 555-1234")
3. Leave Document ID empty or set it
4. Click "Upload & Ingest"
5. View response: "Ingested 5 chunks" (if 2500 chars)

**Or use curl:**

```bash
curl -F "file=@sample.txt" -F "doc_id=my_doc" http://localhost:8001/ingest
```

---

## Example: Scan & Clean

1. Click "Scan Entire Index" → see all PII detected in your Pinecone data
2. Click "Clean & Re-embed" → mask PII and re-upload vectors
3. Run "Scan Entire Index" again → should show PII count dropped to 0

---

## Environment Variables

| Variable           | Purpose                  | Example                                      |
| ------------------ | ------------------------ | -------------------------------------------- |
| `PINECONE_API_KEY` | Pinecone auth            | (in .env)                                    |
| `PINECONE_INDEX`   | Index name to use        | `hybrid-search-langchain-pinecone` (default) |
| `VAULT_SECRET`     | Pseudonym encryption key | Change in production!                        |

---

## Production Considerations

### Security

- `VAULT_SECRET` should come from a KMS (AWS Secrets Manager, HashiCorp Vault, etc.), not hardcoded
- Use environment-specific `.env` files
- Restrict API access with authentication middleware

### Performance

- For 100k+ vectors, use Pinecone's batch operations directly
- Consider namespaces to partition large datasets
- Monitor PII scanning time (linear in index size)

### Compliance

- All cleaning operations are logged in `PseudonymVault`
- Re-hydration requires explicit authorization (call `vault.rectify()`)
- Audit trail survives across restarts (persistent via external KMS)

---

## Troubleshooting

### "No compatible 384D index found"

You've hit the free tier limit. Options:

1. Delete an unused Pinecone index
2. Set `PINECONE_INDEX` to an existing 384D index
3. Upgrade your Pinecone plan

### "source_text not found in metadata"

Vectors in the index don't include the original text. Cleaning degrades to quarantine (delete only). Solution:

1. Re-ingest with the app (it stores source_text automatically)
2. Or manually add `source_text` to vector metadata in Pinecone

### "Presidio not installed"

The app still works, but PII detection falls back to regex only. Optional:

```bash
pip install presidio-analyzer presidio-anonymizer
python -m spacy download en_core_web_lg
```

---

## Next Steps

- **Integrate into your pipeline** — call `/ingest`, `/scan`, `/clean` from your data workflows
- **Custom PII patterns** — extend `aagcp.detect.detector.PIIDetector` with regex or rules
- **Batch operations** — for 1M+ vectors, use Pinecone bulk APIs directly via `store._ix`
- **Advanced retrieval** — add filters in `/query` using Pinecone metadata filters

---

**Created:** 2026-07-04  
**Status:** Production-Ready  
**Author:** AAGCP Team
