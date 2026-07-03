#!/usr/bin/env python3
"""FastAPI backend for AAGCP-Vector PRO frontend dashboard."""
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
import sys, random, os
from pathlib import Path
from typing import Optional, Tuple

sys.path.insert(0, ".")

from dotenv import load_dotenv
load_dotenv()

from aagcp.detect.detector import PIIDetector
from aagcp.embed.embedders import HashingEmbedder, SentenceTransformerEmbedder
from aagcp.store.connectors import (
    InMemoryConnector,
    PineconeConnector,
    VectorRecord,
    VectorStoreConnector,
)
from aagcp.vault import PseudonymVault
from aagcp.scan.scanner import Scanner
from aagcp.migrate.migrator import Migrator
from aagcp.retrieve.retriever import GovernedRetriever

app = FastAPI()

Path("static").mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

# Backend: Pinecone when PINECONE_API_KEY is set, else in-memory demo
backend_mode = "demo"
store: Optional[VectorStoreConnector] = None
embedder = None
index_name: Optional[str] = None
pinecone_namespace: Optional[str] = None

demo_state = {
    "status": "ready",
    "data": None,
    "error": None,
    "backend": "demo",
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

    index_name = os.getenv("PINECONE_INDEX", "hybrid-search-langchain-pinecone")
    pinecone_namespace = os.getenv("PINECONE_NAMESPACE", "")

    try:
        pc = Pinecone(api_key=api_key)
        pinecone_index = pc.index(index_name)
        store = PineconeConnector(pinecone_index, namespace=pinecone_namespace)
        embedder = SentenceTransformerEmbedder("all-MiniLM-L6-v2")
        backend_mode = "pinecone"
        print(
            f"[INIT] Pinecone connected: index={index_name!r}, "
            f"namespace={pinecone_namespace!r}, vectors={store.count()}"
        )
        return True
    except Exception as e:
        print(f"[INIT] Pinecone connection failed: {e} — using demo mode")
        store = None
        embedder = None
        backend_mode = "demo"
        return False


def generate_demo_data() -> Tuple[HashingEmbedder, InMemoryConnector]:
    """Generate 137 fake patient records with PII (fallback when no Pinecone)."""
    FIRST = ["Ramesh","Priya","Arjun","Kavya","Vikram","Ananya","Meera","Sanjay",
             "Divya","Rahul","John","Emma","Liam","Olivia","Noah","Sophia"]
    LAST  = ["Iyer","Sharma","Mehta","Nair","Reddy","Das","Kumar","Smith",
             "Johnson","Williams","Brown","Garcia"]
    COND  = ["Type 2 Diabetes","hypertension","atrial fibrillation","migraine with aura",
             "early nephropathy","peripheral neuropathy","asthma","hyperlipidemia"]

    def aadhaar():
        return f"{random.randint(2000,9999)} {random.randint(1000,9999)} {random.randint(1000,9999)}"

    def pan():
        import string
        return "".join(random.choice(string.ascii_uppercase) for _ in range(5)) + \
               f"{random.randint(1000,9999)}" + random.choice(string.ascii_uppercase)

    emb = HashingEmbedder(384)
    prod = InMemoryConnector()

    N = 137
    random.seed(7)
    for i in range(N):
        fn, ln = random.choice(FIRST), random.choice(LAST)
        cond = random.choice(COND)
        if i % 3 == 0:
            text = (f"Patient {fn} {ln}, Aadhaar {aadhaar()}, phone +91 9{random.randint(100000000,999999999)}, "
                    f"MRN-{random.randint(100000,999999)}, diagnosed with {cond}.")
        elif i % 3 == 1:
            text = (f"Patient {fn} {ln}, PAN {pan()}, email {fn.lower()}.{ln.lower()}@example.com, "
                    f"MRN-{random.randint(100000,999999)}, {cond}.")
        else:
            text = (f"Member {fn} {ln}, SSN {random.randint(100,899)}-{random.randint(10,99)}-{random.randint(1000,9999)}, "
                    f"card 4{random.randint(100000000000000,999999999999999)}, {cond}.")
        prod.upsert([VectorRecord(f"vec_{i:04d}", emb.embed(text), text, {"ingested":"legacy"})])

    return emb, prod


def _get_store_and_embedder() -> Tuple[VectorStoreConnector, object]:
    """Return the active store and embedder (Pinecone or freshly built demo index)."""
    if backend_mode == "pinecone" and store is not None and embedder is not None:
        return store, embedder
    return generate_demo_data()


if _init_pinecone():
    demo_state["backend"] = "pinecone"
else:
    print("[INIT] Demo mode — set PINECONE_API_KEY in .env to scan real Pinecone data")


@app.get("/")
async def root():
    html_path = Path("templates/dashboard.html")
    if html_path.exists():
        return FileResponse(html_path, media_type="text/html")
    return HTMLResponse("<h1>Dashboard not found. Create templates/dashboard.html</h1>")


@app.post("/api/run-demo")
async def run_demo():
    """Run scan → clean → re-scan on Pinecone (if configured) or demo index."""
    try:
        demo_state["status"] = "running"

        prod, emb = _get_store_and_embedder()

        if backend_mode == "pinecone" and prod.count() == 0:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Pinecone index {index_name!r} namespace {pinecone_namespace!r} "
                    "has 0 vectors. Ingest documents first or set PINECONE_NAMESPACE "
                    "to match where your vectors live."
                ),
            )

        detector = PIIDetector(use_presidio=None)
        scanner = Scanner(detector)
        report = scanner.scan(prod, batch=50)
        s = report.summary()

        ANALYST_REVEAL = set()
        ANALYST_PARTIAL = {"AADHAAR":"last4","IN_PHONE":"last4","US_SSN":"last4"}
        vault_secret = os.getenv("VAULT_SECRET")
        secret = (
            vault_secret.encode()
            if isinstance(vault_secret, str)
            else (vault_secret or b"pro-demo-fixed-secret-32-bytes!!")
        )
        vault = PseudonymVault(secret=secret)
        ret_dirty = GovernedRetriever(prod, emb, vault, detector=None)

        queries_before = []
        for h in ret_dirty.query("diabetes patients", ANALYST_REVEAL, ANALYST_PARTIAL, k=5):
            queries_before.append(h.get("source_text", "")[:120])

        migrator = Migrator(detector, vault, emb)
        mrep = migrator.clean(prod, report)

        report2 = scanner.scan(prod, batch=50)
        s2 = report2.summary()

        ret_clean = GovernedRetriever(prod, emb, vault, detector=detector)
        queries_after_analyst = []
        for h in ret_clean.query("diabetes patients", ANALYST_REVEAL, ANALYST_PARTIAL, k=5):
            queries_after_analyst.append(h.get("text", "")[:120])

        queries_after_compliance = []
        for h in ret_clean.query("diabetes patients", {"ALL"}, {}, k=5):
            queries_after_compliance.append(h.get("text", "")[:120])

        demo_state["data"] = {
            "backend": backend_mode,
            "index_name": index_name,
            "namespace": pinecone_namespace,
            "dirty_scan": s,
            "clean_scan": s2,
            "migration_stats": {
                "reembedded": mrep.reembedded,
                "quarantined": mrep.quarantined,
                "tokens_minted": mrep.pii_tokens_minted
            },
            "queries_before": queries_before,
            "queries_after_analyst": queries_after_analyst,
            "queries_after_compliance": queries_after_compliance,
            "detector_coverage": detector.coverage()
        }
        demo_state["status"] = "complete"
        demo_state["error"] = None
        demo_state["backend"] = backend_mode

        return {"status": "success", "data": demo_state["data"]}

    except HTTPException:
        raise
    except Exception as e:
        demo_state["status"] = "error"
        demo_state["error"] = str(e)
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
    uvicorn.run(app, host="0.0.0.0", port=8000)
