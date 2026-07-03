"""
AAGCP + Pinecone Real App
========================

Real working app using the AAGCP core library with Pinecone backend.
- Ingests documents and stores them as vectors in Pinecone
- Scans for PII across the entire index
- Cleans poisoned vectors by re-embedding with masked PII
- Full audit trail with PseudonymVault

This is NOT a demo — it's production-ready with real data and real backends.
"""

import os
import json
from pathlib import Path
from typing import List, Optional
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv

# AAGCP core imports
from aagcp.detect.detector import PIIDetector
from aagcp.embed.embedders import SentenceTransformerEmbedder
from aagcp.store.connectors import PineconeConnector, VectorRecord
from aagcp.vault import PseudonymVault
from aagcp.scan.scanner import Scanner
from aagcp.migrate.migrator import Migrator

load_dotenv()

# Initialize FastAPI
app = FastAPI(title="AAGCP Pinecone Real App")

# Initialize Pinecone connector
try:
    from pinecone import Pinecone
    
    api_key = os.getenv("PINECONE_API_KEY") or os.getenv("pinecode_key")
    if not api_key:
        raise RuntimeError("PINECONE_API_KEY not set")
    
    pc = Pinecone(api_key=api_key)
    
    # Use the 384D index (hybrid-search-langchain-pinecone matches our embedding dim)
    index_name = os.getenv("PINECONE_INDEX", "hybrid-search-langchain-pinecone")
    pinecone_namespace = os.getenv("PINECONE_NAMESPACE", "")
    print(f"[INIT] Connecting to Pinecone index: {index_name}, namespace={pinecone_namespace!r}")
    
    try:
        pinecone_index = pc.index(index_name)
        store = PineconeConnector(pinecone_index, namespace=pinecone_namespace)
        print(f"[INIT] Pinecone connector ready. Current vector count: {store.count()}")
    except Exception as e:
        print(f"[ERROR] Could not connect to index {index_name}: {e}")
        raise
        
except ImportError:
    raise RuntimeError("pinecone package not installed. Run: pip install pinecone")

# Initialize embedder
print("[INIT] Loading SentenceTransformer embedder (all-MiniLM-L6-v2)...")
embedder = SentenceTransformerEmbedder("all-MiniLM-L6-v2")
print(f"[INIT] Embedder dimension: {embedder.dim}")

# Initialize PII detector (auto-uses Presidio if installed)
print("[INIT] Initializing PII Detector...")
detector = PIIDetector()
print(f"[INIT] PII backend: {detector.coverage()}")

# Initialize vault for secure pseudonym handling
vault_secret = os.getenv("VAULT_SECRET", "default-dev-secret-change-in-prod")
vault = PseudonymVault(secret=vault_secret)
print("[INIT] PseudonymVault initialized")

# ────────────────────────────────────────────────────────────────────────────

# Global state for scanning/cleaning
last_scan_report = None
last_clean_report = None

# ────────────────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def dashboard():
    """Serve the dashboard."""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>AAGCP + Pinecone Real App</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }
            .container { max-width: 900px; margin: 0 auto; background: white; padding: 20px; border-radius: 8px; }
            h1 { color: #333; }
            .card { border: 1px solid #ddd; padding: 15px; margin: 10px 0; border-radius: 4px; }
            .btn { background: #007bff; color: white; padding: 10px 15px; border: none; border-radius: 4px; cursor: pointer; }
            .btn:hover { background: #0056b3; }
            .status { padding: 10px; margin: 10px 0; border-radius: 4px; }
            .success { background: #d4edda; color: #155724; }
            .error { background: #f8d7da; color: #721c24; }
            .info { background: #d1ecf1; color: #0c5460; }
            textarea { width: 100%; height: 200px; font-family: monospace; }
            table { width: 100%; border-collapse: collapse; }
            th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
            th { background: #f8f9fa; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🔐 AAGCP + Pinecone Real App</h1>
            <p>Production-ready PII detection, scanning, and cleaning with real Pinecone backend.</p>
            
            <h2>1. Index Status</h2>
            <div class="card">
                <button class="btn" onclick="getStatus()">Get Status</button>
                <div id="status"></div>
            </div>
            
            <h2>2. Ingest Documents</h2>
            <div class="card">
                <form id="uploadForm">
                    <input type="file" id="fileInput" accept=".txt,.pdf,.docx" required>
                    <input type="text" id="documentId" placeholder="Document ID (optional)">
                    <button type="submit" class="btn">Upload & Ingest</button>
                </form>
                <div id="uploadStatus"></div>
            </div>
            
            <h2>3. Scan for PII</h2>
            <div class="card">
                <button class="btn" onclick="scanForPII()">Scan Entire Index</button>
                <div id="scanStatus"></div>
            </div>
            
            <h2>4. Clean Poisoned Vectors</h2>
            <div class="card">
                <button class="btn" onclick="cleanVectors()">Clean & Re-embed</button>
                <div id="cleanStatus"></div>
            </div>
            
            <h2>5. Query</h2>
            <div class="card">
                <textarea id="queryText" placeholder="Enter your query..."></textarea>
                <button class="btn" onclick="queryIndex()">Search</button>
                <div id="queryResults"></div>
            </div>
        </div>
        
        <script>
            async function getStatus() {
                const res = await fetch('/status');
                const data = await res.json();
                document.getElementById('status').innerHTML = \`
                    <div class="status info">
                        <strong>Pinecone Index Status</strong><br>
                        Total vectors: <strong>\${data.total_vectors}</strong><br>
                        Embedding dimension: <strong>\${data.embedding_dim}</strong><br>
                        Index name: <strong>\${data.index_name}</strong>
                    </div>
                \`;
            }
            
            document.getElementById('uploadForm').addEventListener('submit', async (e) => {
                e.preventDefault();
                const file = document.getElementById('fileInput').files[0];
                const docId = document.getElementById('documentId').value || file.name;
                const formData = new FormData();
                formData.append('file', file);
                formData.append('doc_id', docId);
                
                const res = await fetch('/ingest', { method: 'POST', body: formData });
                const data = await res.json();
                document.getElementById('uploadStatus').innerHTML = \`
                    <div class="status \${data.success ? 'success' : 'error'}">
                        <strong>\${data.message}</strong><br>
                        \${data.details ? 'Details: ' + JSON.stringify(data.details) : ''}
                    </div>
                \`;
            });
            
            async function scanForPII() {
                document.getElementById('scanStatus').innerHTML = '<div class="status info">Scanning...</div>';
                const res = await fetch('/scan');
                const data = await res.json();
                document.getElementById('scanStatus').innerHTML = \`
                    <div class="status info">
                        <strong>Scan Complete</strong><br>
                        Total PII detections: <strong>\${data.total_pii}</strong><br>
                        Unique entities: <strong>\${data.unique_entities}</strong><br>
                        High-risk vectors: <strong>\${data.high_risk_count}</strong><br>
                        <pre>\${JSON.stringify(data.summary, null, 2)}</pre>
                    </div>
                \`;
            }
            
            async function cleanVectors() {
                document.getElementById('cleanStatus').innerHTML = '<div class="status info">Cleaning & re-embedding...</div>';
                const res = await fetch('/clean', { method: 'POST' });
                const data = await res.json();
                document.getElementById('cleanStatus').innerHTML = \`
                    <div class="status \${data.success ? 'success' : 'error'}">
                        <strong>\${data.message}</strong><br>
                        Cleaned: \${data.cleaned_count}<br>
                        Quarantined: \${data.quarantined_count}
                    </div>
                \`;
            }
            
            async function queryIndex() {
                const query = document.getElementById('queryText').value;
                const res = await fetch('/query', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ query })
                });
                const data = await res.json();
                document.getElementById('queryResults').innerHTML = \`
                    <div class="status info">
                        <strong>Search Results</strong><br>
                        <table>
                            <tr><th>ID</th><th>Score</th><th>Text (first 100 chars)</th></tr>
                            \${data.results.map(r => \`
                                <tr>
                                    <td>\${r.id}</td>
                                    <td>\${r.score.toFixed(3)}</td>
                                    <td>\${(r.source_text || 'N/A').substring(0, 100)}</td>
                                </tr>
                            \`).join('')}
                        </table>
                    </div>
                \`;
            }
            
            // Load status on page load
            getStatus();
        </script>
    </body>
    </html>
    """

@app.get("/status")
async def status():
    """Get index status."""
    total = store.count()
    return {
        "total_vectors": total,
        "embedding_dim": embedder.dim,
        "index_name": index_name,
        "namespace": pinecone_namespace,
        "pii_detector": detector.coverage()
    }

@app.post("/ingest")
async def ingest(file: UploadFile = File(...), doc_id: str = Form(...)):
    """Ingest a document into the index."""
    try:
        # Read file
        content = await file.read()
        text = content.decode("utf-8", errors="ignore")
        
        # Split into chunks
        chunk_size = 500
        chunks = [text[i:i+chunk_size] for i in range(0, len(text), chunk_size)]
        
        if not chunks:
            return {"success": False, "message": "Empty file"}
        
        # Embed all chunks
        vectors = embedder.embed_batch(chunks)
        
        # Create records with source text
        records = [
            VectorRecord(
                id=f"{doc_id}_chunk_{i}",
                vector=vectors[i],
                source_text=chunk,
                metadata={
                    "doc_id": doc_id,
                    "chunk_idx": i,
                    "filename": file.filename,
                    "total_chunks": len(chunks)
                }
            )
            for i, chunk in enumerate(chunks)
        ]
        
        # Upsert to store
        store.upsert(records)
        
        return {
            "success": True,
            "message": f"Ingested {len(records)} chunks",
            "details": {
                "doc_id": doc_id,
                "filename": file.filename,
                "chunks": len(records),
                "total_vectors_in_index": store.count()
            }
        }
    except Exception as e:
        return {"success": False, "message": str(e)}

@app.get("/scan")
async def scan():
    """Scan entire index for PII."""
    global last_scan_report
    try:
        scanner = Scanner(detector)
        report = scanner.scan(store)
        last_scan_report = report
        
        return {
            "total_pii": report.total,
            "unique_entities": len(set(e["type"] for e in report.entities)),
            "high_risk_count": len([e for e in report.entities if e.get("confidence", 0) > 0.9]),
            "summary": report.summary()
        }
    except Exception as e:
        return {"error": str(e)}

@app.post("/clean")
async def clean():
    """Clean poisoned vectors by re-embedding with masked PII."""
    global last_scan_report, last_clean_report
    try:
        if not last_scan_report:
            # Perform a scan first
            scanner = Scanner(detector)
            last_scan_report = scanner.scan(store)
        
        migrator = Migrator(detector, vault, embedder)
        report = migrator.clean(store, last_scan_report)
        last_clean_report = report
        
        return {
            "success": True,
            "message": "Cleaning complete",
            "cleaned_count": report.cleaned_count if hasattr(report, 'cleaned_count') else 0,
            "quarantined_count": report.quarantined_count if hasattr(report, 'quarantined_count') else 0
        }
    except Exception as e:
        return {"success": False, "message": str(e)}

@app.post("/query")
async def query(request: dict):
    """Query the index."""
    try:
        query_text = request.get("query", "")
        k = request.get("k", 5)
        
        if not query_text:
            return {"error": "query cannot be empty"}
        
        # Embed query
        query_vector = embedder.embed(query_text)
        
        # Search
        results = store.query(query_vector, k=k)
        
        return {
            "query": query_text,
            "results": results,
            "count": len(results)
        }
    except Exception as e:
        return {"error": str(e)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
