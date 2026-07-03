from typing import List

def chunk_text(text: str, chunk_size: int = 400, overlap: int = 50):
    tokens = text.split()  # replace with tokenizer if available
    chunks = []
    start = 0
    while start < len(tokens):
        end = min(start + chunk_size, len(tokens))
        chunk = " ".join(tokens[start:end])
        chunks.append(chunk)
        if end == len(tokens):
            break
        start = end - overlap
    return chunks


import re

# def chunk_by_paragraph(text: str):
#     """
#     Splits text into paragraphs.
#     Paragraphs are separated by one or more blank lines.
#     """
#     paragraphs = [
#         p.strip()
#         for p in re.split(r"\n\n\s*\n", text)
#         if p.strip()
#     ]
#     return paragraphs


def chunk_by_paragraph(text: str) -> List[str]:
    chunks = re.split(
        r'(?=Sample\s+Invoice\s+\d+\s*\nInvoice\s+INV-[A-Z0-9_]+-[A-Z0-9_]+)',
        text
    )
    return [chunk.strip() for chunk in chunks if chunk.strip()]