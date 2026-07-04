import os
import re
from typing import Dict, List, Optional
from dotenv import load_dotenv
from rank_bm25 import BM25Okapi

from sentence_transformers import SentenceTransformer

load_dotenv()

from Data_ingestion.data_ingestion import load_pdf, load_docx, load_excel, load_text
from Data_ingestion.chunking import chunk_text,chunk_by_paragraph
from Data_ingestion.embed import embed_texts
from Data_ingestion.pii import make_sensitive_text, vault, HAS_VAULT, reload_vault_if_needed

from RAG.access import resolve_role, is_allowed

EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"
MASK_PII_FLAG = os.getenv("MASK_PII", "true").strip().lower() in {"1", "true", "yes", "on"}
model = SentenceTransformer(EMBEDDING_MODEL_NAME)
# Use Pinecone by default if configured; fall back to Faiss
from Data_ingestion.vector_store import PineconeIndex

# Require PineconeIndex to be configured; fail fast if not available
DIM = model.get_embedding_dimension()
index = PineconeIndex(dim=DIM, index_name=os.getenv("PINECONE_INDEX"))

def tokenize_text(text: str) -> List[str]:
    return re.findall(r"[a-z0-9]+", text.lower())

def load_file(path: str) -> List[Dict]:
    normalized = path.lower()
    if normalized.endswith(".pdf"):
        return load_pdf(path)
    if normalized.endswith(".docx"):
        return load_docx(path)
    if normalized.endswith(".xlsx") or normalized.endswith(".xls"):
        return load_excel(path)
    if normalized.endswith(".txt"):
        return load_text(path)
    raise ValueError(f"Unsupported file type: {path}")


def prepare_chunks(documents: List[Dict], chunk_size: int = 800, overlap: int = 150, mask_pii: Optional[bool] = None):
    chunks: List[str] = []
    metas: List[Dict] = []
    should_mask_pii = MASK_PII_FLAG if mask_pii is None else mask_pii

    for doc in documents:
        source = doc.get("source", "")
        extra_meta = {k: v for k, v in doc.items() if k not in ("text", "source")}
        for piece in chunk_by_paragraph(doc["text"]):
            masked_piece, masked_spans = make_sensitive_text(piece, mask_pii=should_mask_pii)
            chunks.append(masked_piece)
            metas.append({
                "source": source,
                "text": masked_piece,
                "masked_spans": masked_spans,
                "allowed_roles": ["admin", "finance", "manager", "analyst"],  # Allow all roles by default
                **extra_meta,
            })

    return chunks, metas

bm25 = None
bm25_texts: List[str] = []
bm25_metas: List[Dict] = []

def ingest_file(path: str, chunk_size: int = 800, overlap: int = 150, mask_pii: Optional[bool] = None) -> int:
    global bm25, bm25_texts, bm25_metas
    documents = load_file(path)
    chunks, metas = prepare_chunks(documents, chunk_size=chunk_size, overlap=overlap, mask_pii=mask_pii)

    if not chunks:
        return 0

    vectors = embed_texts(chunks, model)
    index.add(vectors, metas)
    
    # Update BM25 index

    bm25_metas.extend(metas)
    bm25_texts.extend([_bm25_document_text(meta) for meta in metas])
    bm25 = BM25Okapi([tokenize_text(text) for text in bm25_texts])

    return chunks


def ingest_files(paths: List[str], chunk_size: int = 800, overlap: int = 150, mask_pii: Optional[bool] = None) -> int:
    total = 0
    for path in paths:
        total += ingest_file(path, chunk_size=chunk_size, overlap=overlap, mask_pii=mask_pii)
    return total

def _bm25_document_text(meta: Dict) -> str:
    metadata_values = []
    for field in ["source", "page", "invoice_id", "date", "sensitivity_level"]:
        if field in meta:
            metadata_values.append(str(meta[field]))

    for span in meta.get("masked_spans", []):
        original = span.get("original")
        if original:
            metadata_values.append(str(original))

    return f"{meta.get('text','')} {' '.join(metadata_values)}"

def search_question(question: str, role: str, top_k: int = 5, mask_pii: Optional[bool] = None):
    should_mask_pii = MASK_PII_FLAG if mask_pii is None else mask_pii
    _, masked_spans = make_sensitive_text(question, mask_pii=should_mask_pii)
    pii_values = [span["original"] for span in masked_spans]
    print(f"PII detected in question: {pii_values}")

    query_vec = embed_texts([question], model)
    raw_results = index.search(query_vec, k=max(top_k * 2, 20))

    bm25_scores = bm25.get_scores(tokenize_text(question)) if bm25 is not None else None
    id_to_idx = {meta.get("id"): idx for idx, meta in enumerate(bm25_metas) if meta.get("id")}

    scored_results = []
    for hit in raw_results[0]:
        meta = dict(hit.get("meta", {}) or {})
        hit_id = meta.get("id")

        if hit_id and hit_id in id_to_idx:
            local_meta = bm25_metas[id_to_idx[hit_id]]
            meta = {**local_meta, **meta}

        if not is_allowed(role, meta):
            continue

        dense_score = float(hit.get("score", 0.0))
        lexical_score = 0.0
        if bm25_scores is not None and hit_id and hit_id in id_to_idx:
            lexical_score = float(bm25_scores[id_to_idx[hit_id]])

        metadata_score = 0.0
        if should_mask_pii and pii_values:
            matches = sum(
                1
                for pii in pii_values
                if any(pii == span.get("original") for span in meta.get("masked_spans", []))
            )
            metadata_score = matches / len(pii_values)

        combined_score = 0.55 * dense_score + 0.35 * lexical_score + 0.10 * metadata_score
        scored_results.append({"score": combined_score, "meta": meta})

    scored_results.sort(key=lambda x: x["score"], reverse=True)
    
    # Apply vault rehydration per role
    results = scored_results[:top_k]
    if HAS_VAULT and vault:
        reload_vault_if_needed()
        for result in results:
            meta = result["meta"]
            masked_text = meta.get("text", "")

            if role == "admin":
                rehydrated = vault.rehydrate(masked_text, reveal={"ALL"}, partial={})
            elif role in {"finance", "manager"}:
                rehydrated = vault.rehydrate(
                    masked_text,
                    reveal=set(),
                    partial={
                        "AADHAAR": "last4",
                        "IN_PHONE": "last4",
                        "US_SSN": "last4",
                        "PHONE": "last4",
                        "ACCOUNT": "last4",
                        "EMAIL": "last4",
                    },
                )
            else:
                rehydrated = vault.rehydrate(masked_text, reveal=set(), partial={})

            meta["text"] = rehydrated
            print(f"Role: {role} | Rehydrated text sample: {rehydrated[:100]}...")

    return results




def build_prompt(question: str, results: List[Dict], max_chunks: int = 5) -> str:
    context_blocks: List[str] = []
    for hit in results[:max_chunks]:
        meta = hit["meta"]
        chunk_text = meta.get("text", "")
        source = meta.get("source", "unknown")
        context_blocks.append(f"Source: {source}\n{chunk_text}")

    context = "\n\n".join(context_blocks)
    return (
        "You are a helpful assistant. Use the context from the retrieved documents to answer the question. "
        "If the answer is not contained in the context, say you do not know.\n\n"
        f"Context:\n{context}\n\n"
        f"Question: {question}\n\n"
        "Answer:"
    )


def save_index(index_path: str, meta_path: str):
    os.makedirs(os.path.dirname(index_path), exist_ok=True)
    index.save(index_path, meta_path)


def load_index(index_path: str, meta_path: str):
    index.load(index_path, meta_path)


if __name__ == "__main__":
    print("This module defines the RAG workflow. Call ingest_file or search_question from your app.")
