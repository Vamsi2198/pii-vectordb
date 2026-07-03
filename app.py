#!/usr/bin/env python3
"""FastAPI backend for AAGCP-Vector PRO frontend dashboard."""
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
import sys, random, json
from pathlib import Path

sys.path.insert(0, ".")

from aagcp.detect.detector import PIIDetector
from aagcp.embed.embedders import HashingEmbedder
from aagcp.store.connectors import InMemoryConnector, VectorRecord
from aagcp.vault import PseudonymVault
from aagcp.scan.scanner import Scanner
from aagcp.migrate.migrator import Migrator
from aagcp.retrieve.retriever import GovernedRetriever

app = FastAPI()

# Serve static files
Path("static").mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

# Global state
demo_state = {
    "status": "ready",  # ready, running, complete
    "data": None,
    "error": None
}

def generate_demo_data():
    """Generate 137 fake patient records with PII."""
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

@app.get("/")
async def root():
    """Serve dashboard HTML."""
    html_path = Path("templates/dashboard.html")
    if html_path.exists():
        return FileResponse(html_path, media_type="text/html")
    return HTMLResponse("<h1>Dashboard not found. Create templates/dashboard.html</h1>")

@app.post("/api/run-demo")
async def run_demo():
    """Run the full demo pipeline and return results."""
    try:
        demo_state["status"] = "running"
        
        # Build dirty index
        emb, prod = generate_demo_data()
        
        # Scan
        detector = PIIDetector(use_presidio=None)
        scanner = Scanner(detector)
        report = scanner.scan(prod, batch=50)
        s = report.summary()
        
        # Query before cleaning
        ANALYST_REVEAL = set()
        ANALYST_PARTIAL = {"AADHAAR":"last4","IN_PHONE":"last4","US_SSN":"last4"}
        vault = PseudonymVault(secret=b"pro-demo-fixed-secret-32-bytes!!")
        ret_dirty = GovernedRetriever(prod, emb, vault, detector=None)
        
        queries_before = []
        for h in ret_dirty.query("diabetes patients", ANALYST_REVEAL, ANALYST_PARTIAL, k=5):
            queries_before.append(h.get("source_text", "")[:120])
        
        # Clean
        migrator = Migrator(detector, vault, emb)
        mrep = migrator.clean(prod, report)
        
        # Re-scan
        report2 = scanner.scan(prod, batch=50)
        s2 = report2.summary()
        
        # Query after cleaning (analyst view)
        ret_clean = GovernedRetriever(prod, emb, vault, detector=detector)
        queries_after_analyst = []
        for h in ret_clean.query("diabetes patients", ANALYST_REVEAL, ANALYST_PARTIAL, k=5):
            queries_after_analyst.append(h.get("text", "")[:120])
        
        # Query as compliance officer (full reveal)
        queries_after_compliance = []
        for h in ret_clean.query("diabetes patients", {"ALL"}, {}, k=5):
            queries_after_compliance.append(h.get("text", "")[:120])
        
        demo_state["data"] = {
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
        
        return {"status": "success", "data": demo_state["data"]}
    
    except Exception as e:
        demo_state["status"] = "error"
        demo_state["error"] = str(e)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/status")
async def get_status():
    """Get current demo status."""
    return demo_state

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
