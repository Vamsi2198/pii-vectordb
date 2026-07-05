import os
import sys
import tempfile
import time
from pathlib import Path

import streamlit as st

ROOT_DIR = Path(__file__).resolve().parent
RAG_ROOT = ROOT_DIR / "pii-rag-main"
# Allow importing the existing RAG modules from pii-rag-main
sys.path.insert(0, str(RAG_ROOT))

@st.cache_resource
def load_rag_main():
    try:
        import importlib
        rag_main = importlib.import_module("main")
        return rag_main, None
    except Exception as exc:
        return None, exc


def load_file_to_disk(uploaded_file):
    suffix = Path(uploaded_file.name).suffix.lower()
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(uploaded_file.getbuffer())
        return Path(tmp.name)


def render():
    st.title("Claude UI (Streamlit-native)")
    st.write("This page reproduces the `claude_ui.html` features without requiring a separate FastAPI server.")

    rag_main, err = load_rag_main()
    if rag_main is None:
        st.error("RAG module could not be loaded in this environment.")
        if err:
            st.code(str(err))
        return

    # Index status
    st.subheader("RAG Index Status")
    try:
        status = rag_main.index_status()
        st.json(status)
    except Exception as e:
        st.warning(f"Could not fetch index status: {e}")

    st.markdown("---")
    # Load demo data
    if st.button("Load demo RAG data"):
        with st.spinner("Loading demo data..."):
            try:
                res = rag_main.load_demo_data()
                if isinstance(res, dict) and res.get("status") == "success":
                    st.success(res.get("message", "Demo data loaded."))
                else:
                    st.info(str(res))
            except Exception as exc:
                st.error(f"Failed to load demo data: {exc}")

    st.markdown("---")
    st.subheader("Upload document for indexing")
    uploaded_file = st.file_uploader("Upload a file", type=["pdf", "docx", "xlsx", "xls", "txt"]) 
    mask_pii = st.checkbox("Mask PII before indexing", value=True)

    if uploaded_file is not None:
        tmp_path = load_file_to_disk(uploaded_file)
        st.info(f"Saved upload to {tmp_path}")
        try:
            # Prefer workflow.ingest_file if available
            try:
                from RAG.workflow import ingest_file
                count = ingest_file(str(tmp_path), mask_pii=mask_pii)
                st.success(f"Ingested {count} chunks from uploaded file.")
            except Exception:
                # Fallback: prepare_chunks and extend bm25_metas
                chunks, metas = rag_main.prepare_chunks([{"text": tmp_path.read_text(encoding='utf-8', errors='ignore'), "source": uploaded_file.name}], mask_pii=mask_pii)
                try:
                    rag_main.bm25_metas.extend(metas)
                except Exception:
                    pass
                st.success(f"Prepared {len(chunks)} chunks (fallback path).")
        except Exception as exc:
            st.error(f"Indexing failed: {exc}")
        finally:
            try:
                tmp_path.unlink(missing_ok=True)
            except Exception:
                pass

    st.markdown("---")
    st.subheader("Ask a question (RAG)")
    auth_token = st.text_input("Auth token", value="admin_token")
    question = st.text_area("Question", value="What is the PII policy?", height=150)
    mask_query = st.checkbox("Mask PII in query context", value=True)

    if st.button("Run RAG query"):
        if not question.strip():
            st.error("Please enter a question.")
        else:
            with st.spinner("Running query..."):
                try:
                    resp = rag_main.run_query(question, auth_token, mask_query)
                    st.markdown("### Answer")
                    st.write(resp.get("answer", "No answer returned."))

                    if resp.get("retrieved"):
                        st.markdown("### Retrieved Chunks")
                        for i, hit in enumerate(resp["retrieved"], start=1):
                            st.markdown(f"**Chunk {i}** (score {hit.get('score'):.3f})")
                            meta = hit.get("meta", {})
                            st.write(meta.get("text", ""))
                            st.write("---")

                    st.markdown("### Prompt Used")
                    st.code(resp.get("prompt", ""))
                except Exception as exc:
                    st.error(f"RAG query failed: {exc}")


if __name__ == "__main__":
    render()
