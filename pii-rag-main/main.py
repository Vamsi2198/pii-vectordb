import os
import tempfile
import traceback
from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, File, Form, UploadFile, HTTPException, Header, Query
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import openai
import logging

from RAG.workflow import ingest_file, search_question, build_prompt, bm25_metas, prepare_chunks
from RAG.access import resolve_role, is_privileged_role
from Data_ingestion.pii import detokenize_text, HAS_VAULT, vault, VAULT_SECRET_SET, VAULT_STORE_PATH, reload_vault_if_needed, get_vault_info
import hashlib

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("rag_main")

client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

app = FastAPI()
BASE_DIR = Path(__file__).resolve().parent
UPLOADS_DIR = BASE_DIR / "uploads"
UPLOADS_DIR.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
app.mount("/uploads", StaticFiles(directory=UPLOADS_DIR), name="uploads")


@app.on_event("startup")
def startup_reload_vault():
    logger.info("Startup: reloading persisted vault from %s", VAULT_STORE_PATH)
    reload_vault_if_needed()

def run_query(question: str, authorization: str, mask_pii: bool):
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization header missing")

    logger.info(f"[QUERY] question='{question}' auth={authorization} mask_pii={mask_pii}")
    role = resolve_role(authorization)
    logger.info(f"[QUERY] resolved role={role}")
    reload_vault_if_needed()

    results = search_question(question, role, mask_pii=mask_pii)
    logger.info(f"[QUERY] search_question returned {len(results)} results")

    display_results = []

    for hit in results:
        meta = hit["meta"]
        meta_copy = dict(meta)
        text_content = meta.get("text", "")
        meta_copy["text"] = text_content
        display_results.append({"score": hit["score"], "meta": meta_copy})

    logger.info(f"[QUERY] prepared {len(display_results)} display results")
    prompt = build_prompt(question, display_results)

    try:
        response = client.chat.completions.create(
            model="gpt-4-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=300,
        )
        answer = response.choices[0].message.content
    except Exception as e:
        logger.warning(f"[QUERY] OpenAI call failed (continuing anyway): {e}")
        answer = "Could not generate answer (OpenAI unavailable)"

    return {
        "question": question,
        "answer": answer,
        "retrieved": display_results,
        "prompt": prompt,
    }


@app.get("/debug/vault")
def debug_vault():
    if not HAS_VAULT or vault is None:
        return {"status": "no_vault", "message": "Vault is not available in this runtime."}

    reload_vault_if_needed()

    store_sample = []
    for i, (token, entry) in enumerate(vault._store.items()):
        if i >= 20:
            break
        store_sample.append({
            "token": token,
            "type": entry.get("type"),
            "value": entry.get("value"),
            "identities": list(entry.get("identities", [])),
        })

    return {
        "status": "ok",
        "vault_secret_hash": hashlib.sha256(vault.secret).hexdigest(),
        "vault_secret_set": VAULT_SECRET_SET,
        "vault_store_path": VAULT_STORE_PATH,
        "store_size": len(vault._store),
        "shredded_size": len(vault._shredded),
        "store_sample": store_sample,
    }


@app.get("/query")
def query_get(question: str, authorization: str, mask_pii: bool = True):
    return run_query(question, authorization, mask_pii)


@app.post("/query")
def query_post(
    question: str,
    authorization: str,
    mask_pii: bool = True,
):
    return run_query(question, authorization, mask_pii)


@app.get("/", response_class=HTMLResponse)
def home():
    html_path = Path(__file__).resolve().parent / "static" / "index.html"
    return HTMLResponse(html_path.read_text(encoding="utf-8"))


@app.get("/api/index-status")
def index_status():
    """Get status of RAG index."""
    total_chunks = len(bm25_metas) if bm25_metas else 0
    return {
        "total_chunks": total_chunks,
        "status": "ready" if total_chunks > 0 else "empty",
        "message": f"{total_chunks} chunks loaded" if total_chunks > 0 else "No documents ingested yet"
    }


@app.post("/api/load-demo-data")
def load_demo_data():
    """Load sample medical documents into RAG index for testing."""
    try:
        sample_documents = [
            {
                "text": """Patient Medical History Report

On 2023-11-15, Ramesh Iyer, a 51-year-old patient from Mumbai, India, visited Apollo Hospital for his routine diabetes checkup. His Aadhaar number is 234567890123 and his phone number is +91-9876543210.

Medical Summary:
The patient has been a diabetic for 5 years. Current medications include Metformin 500mg twice daily. His recent HbA1c levels were 7.2%, showing improved control.

Lab Results:
- Blood Sugar (Fasting): 125 mg/dL
- Blood Sugar (Post-meal): 185 mg/dL
- Total Cholesterol: 210 mg/dL

Recommendations:
Continue current diabetes management with dietary modifications. Follow-up appointment scheduled for 3 months.

Contact: ramesh.iyer@email.com""",
                "source": "apollo_hospital_patient_001.pdf"
            },
            {
                "text": """Hospital Admission Record

Patient: Priya Sharma
Date of Admission: 2023-10-22
Admission ID: AH-2023-45678
SSN: 123-45-6789

Chief Complaint: Routine physical examination and diabetes screening

Patient Background:
Priya Sharma is a 38-year-old female admitted to Apollo Hospital for her annual diabetes screening. She has a history of Type 2 diabetes diagnosed 3 years ago. Current contact number: +1-555-987-6543.

Vital Signs:
- Blood Pressure: 128/82 mmHg
- Heart Rate: 72 bpm
- Temperature: 98.6°F
- Weight: 68 kg

Assessment:
The patient appears to be managing her diabetes well. Recent blood work shows glucose levels are stable.

Email: priya.sharma@example.com
Insurance: Blue Cross Blue Shield""",
                "source": "apollo_hospital_patient_002.pdf"
            }
        ]
        
        logger.info("Loading %d demo documents into RAG index", len(sample_documents))
        
        # Use the workflow's ingest_file by preparing chunks
        total_chunks_before = len(bm25_metas) if bm25_metas else 0
        
        for doc in sample_documents:
            chunks, metas = prepare_chunks([doc], mask_pii=True)
            bm25_metas.extend(metas)
            logger.info("Added %d chunks from %s", len(chunks), doc['source'])
        
        total_chunks_after = len(bm25_metas) if bm25_metas else 0
        chunks_added = total_chunks_after - total_chunks_before
        
        logger.info("Demo data loaded: added %d chunks, total now %d", chunks_added, total_chunks_after)
        
        return {
            "status": "success",
            "message": f"Loaded {chunks_added} demo chunks",
            "total_chunks": total_chunks_after,
            "documents": len(sample_documents)
        }
        
    except Exception as e:
        logger.error("Failed to load demo data: %s", traceback.format_exc())
        return {
            "status": "error",
            "error": str(e)
        }


@app.post("/api/sync-pinecone-to-rag")
def sync_pinecone_to_rag():
    """Sync data from Pinecone index into RAG's BM25 search index."""
    try:
        logger.info("Starting Pinecone → RAG sync")
        
        total_before = len(bm25_metas) if bm25_metas else 0
        
        # Get all vectors from Pinecone
        from RAG.workflow import index as pinecone_index
        
        # Query to get all vectors (using a generic query that should match everything)
        try:
            # Fetch from Pinecone using the list_all or iter method if available
            all_vectors = []
            
            # Try to get all vectors by querying with a generic vector
            if hasattr(pinecone_index._pine, 'fetch'):
                # Use fetch if available to get metadata
                logger.info("Fetching vectors from Pinecone...")
                # Get vector IDs first by listing
                try:
                    # List namespace contents
                    import json
                    # Create a dummy query to get results
                    dummy_vector = [0.0] * 384  # Default dimension
                    results = pinecone_index._pine.query(
                        vector=dummy_vector,
                        top_k=10000,  # Get as many as possible
                        include_metadata=True,
                        namespace=pinecone_index.namespace
                    )
                    
                    if results and 'matches' in results:
                        logger.info("Found %d vectors in Pinecone", len(results['matches']))
                        
                        for match in results['matches']:
                            meta = match.get('metadata', {})
                            
                            # Create a RAG meta entry from Pinecone metadata
                            rag_meta = {
                                'id': match.get('id'),
                                'text': meta.get('text') or meta.get('source_text') or '',
                                'source': meta.get('source', 'pinecone'),
                                'source_text': meta.get('source_text', ''),
                                'masked_spans': meta.get('masked_spans', []),
                                'allowed_roles': meta.get('allowed_roles', ['admin', 'manager', 'finance', 'analyst']),
                                'pii_masked': meta.get('pii_masked', 0),
                                'governed': meta.get('governed', False),
                                'score': match.get('score', 0.0)
                            }
                            
                            # Add to BM25 index
                            bm25_metas.append(rag_meta)
                            logger.info("Added vector %s from Pinecone", match.get('id')[:20])
                except Exception as e:
                    logger.warning("Could not query Pinecone: %s", e)
                    return {
                        "status": "error",
                        "error": f"Could not query Pinecone: {e}"
                    }
        except Exception as e:
            logger.error("Error accessing Pinecone: %s", e)
            return {
                "status": "error",
                "error": str(e)
            }
        
        total_after = len(bm25_metas) if bm25_metas else 0
        synced = total_after - total_before
        
        logger.info("Sync complete: added %d vectors from Pinecone, total now %d", synced, total_after)
        
        return {
            "status": "success",
            "message": f"Synced {synced} vectors from Pinecone to RAG",
            "total_chunks": total_after,
            "synced_count": synced
        }
        
    except Exception as e:
        logger.error("Sync failed: %s", traceback.format_exc())
        return {
            "status": "error",
            "error": str(e),
            "trace": traceback.format_exc()
        }

@app.post("/upload")
async def upload(file: UploadFile = File(...), mask_pii: bool = Form(True)):
    content = await file.read()
    safe_name = Path(file.filename).name
    save_path = UPLOADS_DIR / safe_name
    with open(save_path, "wb") as f:
        f.write(content)

    chunk_count = ingest_file(str(save_path), mask_pii=mask_pii)
    preview_url = f"/uploads/{safe_name}"
    return JSONResponse({
        "status": "saved",
        "chunks": chunk_count,
        "filename": safe_name,
        "preview_url": preview_url,
        "mask_pii": mask_pii,
    })


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)