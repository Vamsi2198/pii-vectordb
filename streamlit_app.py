import os
import sys
import tempfile
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

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

    tab = st.tabs(["PII Masking", "RAG Retrieval", "Full UI"])

    with tab[0]:
        render_masking_tab()

    with tab[1]:
        render_rag_tab()

    with tab[2]:
        st.header("Full Claude UI")
        st.write(
            "Display the existing `templates/claude_ui.html` UI from your deployed FastAPI backend. "
            "Enter the backend’s public URL in API_BASE and use iframe mode."
        )
        default_api_base = st.secrets.get("API_BASE") if hasattr(st, "secrets") else None
        if not default_api_base:
            default_api_base = os.getenv("API_BASE", "")
        api_base = st.text_input("API base URL (include scheme)", value=default_api_base)
        if not api_base:
            st.warning(
                "API_BASE is not configured. Enter the public URL of your deployed FastAPI backend, e.g. https://my-backend.onrender.com"
            )
        elif api_base.startswith("http://localhost") or api_base.startswith("https://localhost"):
            st.warning(
                "Localhost only works when Streamlit and FastAPI run on the same machine. "
                "For remote use, set API_BASE to your deployed backend URL."
            )

        if api_base:
            st.info("Embedding the backend UI from your deployed FastAPI host.")
            components.iframe(api_base.rstrip("/") + "/", height=1100)
        else:
            st.error("Please enter your deployed FastAPI backend URL in API_BASE.")


if __name__ == "__main__":
    render_page()
