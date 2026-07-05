import os
import sys
import tempfile
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv
import subprocess
import socket
import time

ROOT_DIR = Path(__file__).resolve().parent
RAG_ROOT = ROOT_DIR / "pii-rag-main"

# Load .env from the repo root if it exists
load_dotenv(dotenv_path=ROOT_DIR / ".env")
# Also load .env from the pii-rag-main subfolder if present
load_dotenv(dotenv_path=RAG_ROOT / ".env", override=False)

# Streamlit Cloud secrets are often set in st.secrets rather than in os.environ.
# Mirror them to environment variables so downstream imports that use os.getenv() work.
for secret_key in (
    "PINECONE_API_KEY",
    "pinecode_key",
    "OPENAI_API_KEY",
    "VAULT_SECRET",
    "PINECONE_INDEX",
    "PINECONE_ENVIRONMENT",
    "VAULT_STORE_PATH",
):
    if not os.getenv(secret_key) and secret_key in st.secrets:
        os.environ[secret_key] = str(st.secrets[secret_key])

# Allow importing the existing RAG modules from pii-rag-main
sys.path.insert(0, str(RAG_ROOT))

from Data_ingestion.pii import make_sensitive_text, HAS_VAULT, vault, reload_vault_if_needed
import streamlit.components.v1 as components
from Data_ingestion.data_ingestion import load_pdf, load_docx, load_excel, load_text

st.set_page_config(page_title="AAGCP Streamlit", layout="wide")


def load_file_content(uploaded_file):
    suffix = Path(uploaded_file.name).suffix.lower()
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(uploaded_file.getbuffer())
        tmp_path = Path(tmp.name)

    if suffix == ".pdf":
        docs = load_pdf(str(tmp_path))
    elif suffix == ".docx":
        docs = load_docx(str(tmp_path))
    elif suffix in {".xlsx", ".xls"}:
        docs = load_excel(str(tmp_path))
    elif suffix == ".txt":
        docs = load_text(str(tmp_path))
    else:
        raise ValueError(f"Unsupported file type: {suffix}")

    return docs, tmp_path


@st.cache_resource
def load_rag_module():
    try:
        import importlib
        rag_main = importlib.import_module("main")
        return rag_main, None
    except Exception as exc:
        return None, exc


def render_masking_tab():
    st.header("PII Masking Dashboard")
    uploaded_file = st.file_uploader(
        "Upload a document to mask PII", type=["pdf", "docx", "xlsx", "xls", "txt"]
    )
    mask_pii = st.checkbox("Mask PII before display", value=True)

    if uploaded_file is None:
        st.info("Upload a file to preview masked output.")
        return

    try:
        docs, tmp_path = load_file_content(uploaded_file)
    except ValueError as exc:
        st.error(str(exc))
        return

    if not docs:
        st.warning("No text was extracted from the uploaded file.")
        return

    st.success(f"Extracted {len(docs)} text block(s) from {uploaded_file.name}")
    st.markdown("---")

    for idx, doc in enumerate(docs, start=1):
        masked_text, masked_spans = make_sensitive_text(doc["text"], mask_pii=mask_pii)
        with st.expander(f"Block {idx}: {doc.get('source', '')}", expanded=idx == 1):
            st.write(masked_text)
            if masked_spans:
                st.markdown("**Detected tokens**")
                st.table(masked_spans)
            else:
                st.info("No PII tokens detected in this block.")

    if tmp_path.exists():
        tmp_path.unlink(missing_ok=True)


def render_rag_tab():
    st.header("RAG Retrieval UI")
    rag_main, rag_error = load_rag_module()

    if rag_main is None:
        st.warning(
            "RAG functionality is not available in this environment. "
            "This usually means PINECONE_API_KEY is not set or dependencies are missing."
        )
        if rag_error:
            st.code(str(rag_error))
        return

    if st.button("Load demo RAG data"):
        result = rag_main.load_demo_data()
        if result.get("status") == "success":
            st.success(result.get("message"))
        else:
            st.error(result)

    st.markdown("---")
    with st.expander("RAG Index Status"):
        status = rag_main.index_status()
        st.json(status)

    st.subheader("Upload file for RAG indexing")
    uploaded_file = st.file_uploader(
        "Upload a file for RAG ingestion", type=["pdf", "docx", "xlsx", "xls", "txt"], key="rag_upload"
    )
    rag_mask_pii = st.checkbox("Mask PII before indexing", value=True, key="rag_mask")

    if uploaded_file is not None:
        docs, tmp_path = load_file_content(uploaded_file)
        total_chunks = 0
        for doc in docs:
            chunks, metas = rag_main.prepare_chunks([doc], mask_pii=rag_mask_pii)
            total_chunks += len(chunks)
            rag_main.bm25_metas.extend(metas)
        st.success(f"Prepared {total_chunks} chunk(s) from uploaded file.")
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)

    st.markdown("---")
    st.subheader("Ask a question")
    auth_token = st.text_input("Auth token", value="admin_token")
    question = st.text_area("Question", value="What is the PII policy?", height=120)
    rag_mask_pii = st.checkbox("Mask PII in query context", value=True, key="rag_query_mask")

    if st.button("Run RAG query"):
        if not question.strip():
            st.error("Please enter a question.")
        else:
            try:
                response = rag_main.run_query(question, auth_token, rag_mask_pii)
                st.markdown("### Answer")
                st.write(response.get("answer", "No answer returned."))
                if response.get("retrieved"):
                    st.markdown("### Retrieved Chunks")
                    for i, hit in enumerate(response["retrieved"], start=1):
                        st.markdown(f"**Chunk {i}** (score {hit.get('score'):.3f})")
                        st.write(hit["meta"].get("text", ""))
                        st.write("---")
                st.markdown("### Prompt Used")
                st.code(response.get("prompt", ""))
            except Exception as exc:
                st.error(f"RAG query failed: {exc}")


def render_page():
    st.title("AAGCP Streamlit App")
    st.write(
        "This Streamlit wrapper reuses the existing masking and RAG logic from the repo. "
        "The RAG tab requires the same environment variables and dependencies as the existing FastAPI app."
    )

    tab = st.tabs(["PII Masking", "RAG Retrieval", "Full UI (optional)"])

    with tab[0]:
        render_masking_tab()

    with tab[1]:
        render_rag_tab()

    with tab[2]:
        st.header("Full Claude UI (optional)")
        st.write(
            "This tab calls the backend APIs directly. Set `API_BASE` to your running FastAPI host "
            "(for example http://127.0.0.1:8000) and then use the controls below."
        )

        api_base = st.text_input("API base URL", value=(st.secrets.get("API_BASE") if hasattr(st, "secrets") else os.getenv("API_BASE", "")))
        if api_base:
            api_base = api_base.rstrip("/")

        try:
            import requests
        except Exception:
            st.error("The `requests` package is required for API mode. Install it in your environment.")
            return

        def api_url(path: str) -> str:
            return f"{api_base}{path}"

        col1, col2 = st.columns([1, 2])

        with col1:
            st.subheader("Backend actions")
            if st.button("Get /api/status"):
                if not api_base:
                    st.error("Set API base URL first")
                else:
                    try:
                        r = requests.get(api_url("/api/status"), timeout=20)
                        st.json(r.json())
                    except Exception as e:
                        st.error(f"Status request failed: {e}")

            if st.button("Run /api/run-demo"):
                if not api_base:
                    st.error("Set API base URL first")
                else:
                    try:
                        r = requests.post(api_url("/api/run-demo"), timeout=120)
                        st.json(r.json())
                    except Exception as e:
                        st.error(f"Run-demo failed: {e}")

            if st.button("/rag/api/load-demo-data"):
                if not api_base:
                    st.error("Set API base URL first")
                else:
                    try:
                        r = requests.post(api_url("/rag/api/load-demo-data"), timeout=60)
                        st.json(r.json())
                    except Exception as e:
                        st.error(f"Load-demo failed: {e}")

        with col2:
            st.subheader("Upload file to RAG (/rag/upload)")
            upload_file = st.file_uploader("Choose file to upload to RAG UI", type=["pdf", "docx", "xlsx", "xls", "txt"], key="fullui_upload")
            mask_pii = st.checkbox("Mask PII before upload", value=True, key="fullui_mask")
            if st.button("Upload to /rag/upload"):
                if not api_base:
                    st.error("Set API base URL first")
                elif upload_file is None:
                    st.error("Choose a file first")
                else:
                    try:
                        files = {"file": (upload_file.name, upload_file.getvalue())}
                        data = {"mask_pii": str(mask_pii)}
                        r = requests.post(api_url("/rag/upload"), files=files, data=data, timeout=120)
                        st.json(r.json())
                    except Exception as e:
                        st.error(f"Upload failed: {e}")

            st.markdown("---")
            st.subheader("Run RAG query")
            auth_token = st.text_input("Auth token", value="admin_token", key="fullui_auth")
            question = st.text_area("Question", value="What is the PII policy?", height=120, key="fullui_q")
            mask_query = st.checkbox("Mask PII in query context", value=True, key="fullui_qmask")
            if st.button("Call /rag/query"):
                if not api_base:
                    st.error("Set API base URL first")
                elif not question.strip():
                    st.error("Enter a question")
                else:
                    try:
                        params = {"question": question, "authorization": auth_token, "mask_pii": str(mask_query)}
                        r = requests.get(api_url("/rag/query"), params=params, timeout=60)
                        st.json(r.json())
                    except Exception as e:
                        st.error(f"RAG query failed: {e}")

        st.markdown("---")
        st.info("Note: this tab calls your FastAPI backend directly. Run `uvicorn app:app --host 0.0.0.0 --port 8000` on the machine hosting the API and set `API base URL` accordingly.")


if __name__ == "__main__":
    render_page()
