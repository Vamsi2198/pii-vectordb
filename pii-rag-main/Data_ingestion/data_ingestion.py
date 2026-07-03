import pdfplumber
import docx
import pandas as pd
from Data_ingestion.pii import make_sensitive_text

def load_pdf(path):
    text = []
    with pdfplumber.open(path) as pdf:
        for i, page in enumerate(pdf.pages, start=1):
            page_text = page.extract_text() or ""
            if page_text.strip():
                text.append({
                    "text": page_text,
                    "source": path,
                    "page": i,
                    "sensitivity_level": "high",
                    "allowed_roles": ["admin", "manager", "finance"],
                })
    return text

def load_docx(path):
    doc = docx.Document(path)
    paragraphs = []
    for i, para in enumerate(doc.paragraphs, start=1):
        if para.text.strip():
            paragraphs.append({"text": para.text, "source": path, "paragraph": i})
    return paragraphs

def load_excel(path):
    df = pd.read_excel(path, engine="openpyxl")
    rows = []
    for i, row in df.iterrows():
        row_text = " ".join(str(x) for x in row.values if pd.notna(x))
        if row_text.strip():
            rows.append({"text": row_text, "source": path, "row": int(i + 1)})
    return rows

def load_text(path):
    with open(path, "r", encoding="utf-8") as f:
        return [{"text": f.read(), "source": path}]