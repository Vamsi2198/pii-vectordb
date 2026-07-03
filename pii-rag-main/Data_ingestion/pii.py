import re
from typing import Dict, List, Tuple


PII_patterns = {
    "PHONE": re.compile(r"\+?\d[d\-s]{7,}\d"),
    "ACCOUNT": re.compile(r"\b\d{4,12}\b"),
    "EMAIL": re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"),
}

def make_sensitive_text(text: str, mask_pii: bool = True) -> Tuple[str, List[Dict]]:
    if not mask_pii:
        return text, []

    masked_spans = []
    masked_text = text

    for label, pattern in PII_patterns.items():
        for match in pattern.finditer(masked_text):
            token_id = f"{label}_{len(masked_spans) + 1:03d}"
            span_text = match.group(0)
            masked_text = masked_text.replace(span_text, token_id, 1)
            masked_spans.append({
                "token": token_id,
                "label": label,
                "original": span_text,
            })

    return masked_text, masked_spans



def detokenize_text(text:str, masked_spans: List[Dict]) -> str:
    detokenized = text
    for span in masked_spans:
        detokenized = detokenized.replace(span["token"], span["original"])
    return detokenized

