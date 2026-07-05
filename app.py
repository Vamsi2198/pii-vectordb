#!/usr/bin/env python3
"""FastAPI backend for AAGCP-Vector PRO frontend dashboard."""
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.cors import CORSMiddleware
import logging
import traceback
import importlib.util
import sys, os
from pathlib import Path
from typing import Optional

sys.path.insert(0, ".")

from dotenv import load_dotenv
load_dotenv()

from aagcp.detect.detector import PIIDetector
from aagcp.embed.embedders import HashingEmbedder, SentenceTransformerEmbedder
from aagcp.store.connectors import PineconeConnector, VectorRecord, VectorStoreConnector
from aagcp.vault import PseudonymVault
from aagcp.scan.scanner import Scanner
from aagcp.migrate.migrator import Migrator
from aagcp.retrieve.retriever import GovernedRetriever

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

template_root = Path(__file__).resolve().parent / "templates"
static_root = Path(__file__).resolve().parent / "static"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("aagcp_app")
# sdksm
static_root.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_root)), name="static")

# Mount the RAG app from the pii-rag-main folder at /rag
rag_root = Path(__file__).resolve().parent / "pii-rag-main"
rag_main_file = rag_root / "main.py"
if rag_main_file.exists():
    sys.path.insert(0, str(rag_root))
    spec = importlib.util.spec_from_file_location("rag_main_module", str(rag_main_file))
    rag_main_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(rag_main_module)
    app.mount("/rag", rag_main_module.app)
    logger.info("Mounted RAG app at /rag")
else:
    logger.warning("Could not mount RAG app because %s does not exist", rag_main_file)

# Backend: Pinecone when PINECONE_API_KEY is set, otherwise the app stays offline
backend_mode = "disabled"
store: Optional[VectorStoreConnector] = None
embedder = None
index_name: Optional[str] = None
pinecone_namespace: Optional[str] = None

demo_state = {
    "status": "ready",
    "data": None,
    "error": None,
    "backend": "disabled",
}


def _init_pinecone() -> bool:
    """Connect to Pinecone using .env credentials. Returns True on success."""
    global store, embedder, backend_mode, index_name, pinecone_namespace

    api_key = os.getenv("PINECONE_API_KEY") or os.getenv("pinecode_key")
    if not api_key:
        return False

    try:
        from pinecone import Pinecone
    except ImportError:
        print("[INIT] pinecone package not installed — using demo mode")
        return False

    index_name = os.getenv("PINECONE_INDEX", "ragpii-384")
    pinecone_namespace = os.getenv("PINECONE_NAMESPACE", "")

    try:
        pc = Pinecone(api_key=api_key)
        pinecone_index = pc.index(index_name)
        store = PineconeConnector(pinecone_index, namespace=pinecone_namespace)
        try:
            embedder = SentenceTransformerEmbedder("all-MiniLM-L6-v2")
            logger.info("Using SentenceTransformer embedder")
        except Exception as embed_err:
            embedder = HashingEmbedder(384)
            logger.warning("SentenceTransformer unavailable; using hashing embedder: %s", embed_err)
        backend_mode = "pinecone"
        logger.info(
            "Pinecone connected: index=%r namespace=%r vectors=%s",
            index_name, pinecone_namespace, store.count()
        )
        return True
    except Exception as e:
        logger.exception("Pinecone connection failed — switching backend")
        store = None
        embedder = None
        backend_mode = "demo"
        return False


def _chunk_text(text: str, chunk_size: int = 500) -> list[str]:
    """Split a text blob into manageable chunks for embedding and ingestion."""
    if not text:
        return []
    return [text[i : i + chunk_size] for i in range(0, len(text), chunk_size)]


def _ingest_text_to_store(text: str, doc_id: str = "live-doc") -> dict:
    """Embed a text payload and upsert it into the live Pinecone index."""
    if backend_mode != "pinecone" or store is None or embedder is None:
        raise HTTPException(status_code=400, detail="Pinecone is not configured")

    chunks = _chunk_text(text)
    if not chunks:
        raise HTTPException(status_code=400, detail="Input text is empty")

    vectors = embedder.embed_batch(chunks)
    records = [
        VectorRecord(
            id=f"{doc_id}_chunk_{idx}",
            vector=vectors[idx],
            source_text=chunk,
            metadata={"doc_id": doc_id, "chunk_idx": idx, "source": "live_ingest"},
        )
        for idx, chunk in enumerate(chunks)
    ]
    store.upsert(records)
    return {"doc_id": doc_id, "chunks": len(records), "vector_count": store.count()}


if _init_pinecone():
    demo_state["backend"] = "pinecone"
else:
    print("[INIT] Pinecone not configured — set PINECONE_API_KEY in .env to use the live backend")


@app.get("/")
async def root():
    html_path = template_root / "claude_ui.html"
    if html_path.exists():
        return FileResponse(html_path, media_type="text/html")
    html_path = template_root / "dashboard.html"
    if html_path.exists():
        return FileResponse(html_path, media_type="text/html")
    return HTMLResponse("<h1>Dashboard not found. Create templates/claude_ui.html or templates/dashboard.html</h1>")


@app.get("/ui")
async def ui_page():
    html_path = template_root / "claude_ui.html"
    if html_path.exists():
        return FileResponse(html_path, media_type="text/html")
    return HTMLResponse("<h1>Claude UI not found. Create templates/claude_ui.html</h1>")


@app.get("/rag-test")
async def rag_test_page():
    """Serve the RAG query test page."""
    html_path = Path("templates/rag_test.html")
    if html_path.exists():
        return FileResponse(html_path, media_type="text/html")
    return HTMLResponse("<h1>RAG Test page not found</h1>")


@app.post("/api/run-demo")
async def run_demo():
    """Run the real AAGCP scan → clean → re-scan workflow on the live Pinecone index."""
    try:
        demo_state["status"] = "running"
        logger.info("run_demo started: backend=%s, index=%s, namespace=%s", backend_mode, index_name, pinecone_namespace)

        if backend_mode != "pinecone" or store is None or embedder is None:
            raise HTTPException(status_code=400, detail="Pinecone is not configured")

        count = store.count()
        logger.info("Pinecone vector count = %s", count)
        if count == 0:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Pinecone index {index_name!r} namespace {pinecone_namespace!r} "
                    "has 0 vectors. Ingest documents first to run the live workflow."
                ),
            )

        detector = PIIDetector(use_presidio=None)
        scanner = Scanner(detector)
        logger.info("Starting scan on %s vectors", count)
        report = scanner.scan(store, batch=50)
        s = report.summary()
        logger.info("Scan complete: %s", s)

        ANALYST_REVEAL = set()
        ANALYST_PARTIAL = {"AADHAAR": "last4", "IN_PHONE": "last4", "US_SSN": "last4"}
        vault_secret = os.getenv("VAULT_SECRET")
        secret = (
            vault_secret.encode()
            if isinstance(vault_secret, str)
            else (vault_secret or b"pro-demo-fixed-secret-32-bytes!!")
        )
        vault_store_path = os.getenv("VAULT_STORE_PATH")
        if vault_store_path:
            vault_store_path = Path(vault_store_path)
        else:
            vault_store_path = Path(".vault_store.json")
        vault = PseudonymVault(path=str(vault_store_path), secret=secret)
        ret_dirty = GovernedRetriever(store, embedder, vault, detector=None)

        # Retrieve and log hit shapes for debugging (helps catch missing fields)
        hits_before = ret_dirty.query("diabetes patients", ANALYST_REVEAL, ANALYST_PARTIAL, k=5)
        logger.info("Hits before cleaning: count=%s, sample_keys=%s",
                    len(hits_before), [list(dict(h).keys()) for h in hits_before[:5]])
        queries_before = []
        for h in hits_before:
            # Extract text from rehydrated field (role-based masking already applied)
            txt = h.get("text") or h.get("source_text") or ""
            queries_before.append(txt)
        logger.info("Queries before cleaning computed: %s results", len(queries_before))

        migrator = Migrator(detector, vault, embedder)
        logger.info("Starting migration / clean step")
        mrep = migrator.clean(store, report)
        logger.info("Migration complete: %s", mrep)

        report2 = scanner.scan(store, batch=50)
        s2 = report2.summary()
        logger.info("Rescan complete: %s", s2)

        ret_clean = GovernedRetriever(store, embedder, vault, detector=detector)
        hits_after_analyst = ret_clean.query("diabetes patients", ANALYST_REVEAL, ANALYST_PARTIAL, k=5)
        logger.info("Hits after analyst: count=%s, sample_keys=%s",
                    len(hits_after_analyst), [list(dict(h).keys()) for h in hits_after_analyst[:5]])
        queries_after_analyst = []
        for h in hits_after_analyst:
            # Extract text with analyst-role masking applied by retriever
            txt = h.get("text") or h.get("source_text") or ""
            queries_after_analyst.append(txt)
        logger.info("Queries after analyst computed: %s results", len(queries_after_analyst))

        hits_after_compliance = ret_clean.query("diabetes patients", {"ALL"}, {}, k=5)
        logger.info("Hits after compliance: count=%s, sample_keys=%s",
                    len(hits_after_compliance), [list(dict(h).keys()) for h in hits_after_compliance[:5]])
        queries_after_compliance = []
        for h in hits_after_compliance:
            # Extract text with compliance-role full reveal applied by retriever
            txt = h.get("text") or h.get("source_text") or ""
            queries_after_compliance.append(txt)
        logger.info("Queries after compliance computed: %s results", len(queries_after_compliance))

        demo_state["data"] = {
            "backend": backend_mode,
            "index_name": index_name,
            "namespace": pinecone_namespace,
            "dirty_scan": s,
            "clean_scan": s2,
            "migration_stats": {
                "reembedded": mrep.reembedded,
                "quarantined": mrep.quarantined,
                "tokens_minted": mrep.pii_tokens_minted,
            },
            "queries_before": queries_before,
            "queries_after_analyst": queries_after_analyst,
            "queries_after_compliance": queries_after_compliance,
            "detector_coverage": detector.coverage(),
        }
        demo_state["status"] = "complete"
        demo_state["error"] = None
        demo_state["backend"] = backend_mode

        return {"status": "success", "data": demo_state["data"]}

    except HTTPException:
        raise
    except Exception as e:
        trace = traceback.format_exc()
        logger.error("run_demo failed: %s", trace)
        demo_state["status"] = "error"
        demo_state["error"] = trace
        raise HTTPException(status_code=500, detail=f"Internal server error: {e}")


@app.get("/api/test-rag-query")
async def test_rag_query(question: str = "who came to Apollo Hospital for diabetes checkup"):
    """Test RAG query endpoint to verify chunks are returned with vault masking."""
    try:
        sys.path.insert(0, "pii-rag-main")
        from RAG.workflow import search_question, bm25_metas
        from RAG.access import resolve_role
        
        logger.info("RAG query test: question=%s, index_size=%s", question, len(bm25_metas) if bm25_metas else 0)
        
        if not bm25_metas or len(bm25_metas) == 0:
            return {
                "status": "no_data",
                "message": "RAG index is empty - no documents ingested yet",
                "chunks_in_index": 0,
                "query": question
            }
        
        # Test with ANALYST_PARTIAL role
        results_analyst = search_question(question, role='ANALYST_PARTIAL', top_k=5)
        logger.info("RAG ANALYST results: %s", len(results_analyst))
        
        analyst_results = []
        for result in results_analyst[:3]:
            meta = result.get('meta', {})
            analyst_results.append({
                "score": result.get('score'),
                "text": meta.get('text', '')[:200],  # First 200 chars
                "source": meta.get('source'),
                "role": "ANALYST_PARTIAL (masked)"
            })
        
        # Test with COMPLIANCE role
        results_compliance = search_question(question, role='COMPLIANCE', top_k=5)
        logger.info("RAG COMPLIANCE results: %s", len(results_compliance))
        
        compliance_results = []
        for result in results_compliance[:3]:
            meta = result.get('meta', {})
            compliance_results.append({
                "score": result.get('score'),
                "text": meta.get('text', '')[:200],  # First 200 chars
                "source": meta.get('source'),
                "role": "COMPLIANCE (full reveal)"
            })
        
        return {
            "status": "success",
            "query": question,
            "chunks_in_index": len(bm25_metas),
            "analyst_partial_results": analyst_results,
            "compliance_results": compliance_results,
            "total_results_found": len(results_analyst)
        }
        
    except Exception as e:
        logger.error("RAG query test failed: %s", traceback.format_exc())
        return {
            "status": "error",
            "error": str(e),
            "trace": traceback.format_exc()
        }


@app.post("/api/ingest")
async def ingest_live(payload: dict):
    """Ingest a JSON payload of text into the live Pinecone index."""
    try:
        text = payload.get("text", "")
        doc_id = payload.get("doc_id") or "live-doc"
        result = _ingest_text_to_store(text, doc_id=doc_id)
        return {"status": "success", **result}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/ingest-file")
async def ingest_file_endpoint(file: UploadFile = File(...), doc_id: Optional[str] = Form(None)):
    """Accept an uploaded file (PDF or text), extract text, and ingest into the live store."""
    try:
        # Read file contents
        filename = file.filename or doc_id or 'uploaded'
        content_type = (file.content_type or '').lower()

        text = None
        # Handle PDF extraction
        if content_type == 'application/pdf' or filename.lower().endswith('.pdf'):
            try:
                import PyPDF2
            except ImportError:
                raise HTTPException(status_code=500, detail="PyPDF2 not installed; cannot extract PDF text. Add PyPDF2 to requirements.txt and install.")
            try:
                # file.file is a SpooledTemporaryFile or similar
                reader = PyPDF2.PdfReader(file.file)
                pages = [p.extract_text() or '' for p in reader.pages]
                text = '\n'.join(pages)
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"PDF extraction failed: {e}")
        else:
            # Fallback: read as text
            raw = await file.read()
            try:
                text = raw.decode('utf-8')
            except Exception:
                # try latin-1
                try:
                    text = raw.decode('latin-1')
                except Exception:
                    raise HTTPException(status_code=400, detail="Could not decode uploaded file as text")

        if not text or text.strip() == '':
            raise HTTPException(status_code=400, detail="No text extracted from uploaded file")

        result = _ingest_text_to_store(text, doc_id=doc_id or filename)
        return {"status": "success", **result}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/status")
async def get_status():
    """Get current pipeline status and backend info."""
    info = {
        **demo_state,
        "backend": backend_mode,
        "index_name": index_name,
        "namespace": pinecone_namespace,
    }
    if backend_mode == "pinecone" and store is not None:
        info["vector_count"] = store.count()
    return info


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
