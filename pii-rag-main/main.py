import os
import tempfile
from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, File, Form, UploadFile, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import openai

from RAG.workflow import ingest_file, search_question, build_prompt
from RAG.access import resolve_role, is_privileged_role
from Data_ingestion.pii import detokenize_text
client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

app = FastAPI()
BASE_DIR = Path(__file__).resolve().parent
UPLOADS_DIR = BASE_DIR / "uploads"
UPLOADS_DIR.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
app.mount("/uploads", StaticFiles(directory=UPLOADS_DIR), name="uploads")

@app.get("/query")
def query(question: str, authorization: str, mask_pii: bool = True):
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization header missing")
    
    role = resolve_role(authorization)
    results = search_question(question, role, mask_pii=mask_pii)
    should_detokenize = mask_pii and not is_privileged_role(role)

    display_results = []
    for hit in results:
        meta = hit["meta"]
        meta_copy = dict(meta)
        if should_detokenize:
            meta_copy["text"] = detokenize_text(meta.get("text", ""), meta.get("masked_spans", []))
        else:
            meta_copy["text"] = meta.get("text", "")
        display_results.append({"score": hit["score"], "meta": meta_copy})

    prompt = build_prompt(question, display_results)
    response = client.responses.create(
        model="gpt-4.1-mini",
        input=prompt,
        temperature=0.0,
        max_output_tokens=300,
    )

    answer = response.output_text

    return {
        "question": question,
        "answer": answer,
        "retrieved": display_results,
        "prompt": prompt,
    }


@app.get("/", response_class=HTMLResponse)
def home():
    html_path = Path(__file__).resolve().parent / "static" / "index.html"
    return HTMLResponse(html_path.read_text(encoding="utf-8"))

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
    uvicorn.run(app, host="0.0.0.0", port=8000)