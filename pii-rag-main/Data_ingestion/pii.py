import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Tuple

# Ensure the workspace root is on sys.path so sibling package `aagcp` can be imported
ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# Import vault from parent aagcp module
try:
    from aagcp.vault import PseudonymVault
    from aagcp.detect.detector import Finding
    HAS_VAULT = True
except ImportError:
    HAS_VAULT = False

# Initialize vault if available
DEFAULT_VAULT_SECRET = b"pro-demo-fixed-secret-32-bytes!!"
vault = None
VAULT_SECRET_SET = False
VAULT_STORE_PATH = None
if HAS_VAULT:
    vault_secret = os.getenv("VAULT_SECRET")
    VAULT_SECRET_SET = vault_secret is not None
    secret = (
        vault_secret.encode() if isinstance(vault_secret, str) else DEFAULT_VAULT_SECRET
    )
    vault_path = os.getenv("VAULT_STORE_PATH")
    if vault_path:
        vault_path = Path(vault_path)
    else:
        vault_path = ROOT_DIR / ".vault_store.json"
    VAULT_STORE_PATH = str(vault_path)
    vault = PseudonymVault(path=str(vault_path), secret=secret)

def reload_vault_if_needed():
    global vault
    if not HAS_VAULT or vault is None or vault.path is None:
        return
    if vault.path.exists():
        try:
            vault._load()
        except Exception:
            pass

def get_vault_info():
    if not HAS_VAULT or vault is None:
        return {
            "has_vault": False,
            "vault_secret_set": False,
            "vault_store_path": None,
            "vault_file_exists": False,
            "store_size": 0,
            "shredded_size": 0,
        }
    return {
        "has_vault": True,
        "vault_secret_set": VAULT_SECRET_SET,
        "vault_store_path": VAULT_STORE_PATH,
        "vault_file_exists": vault.path.exists() if vault.path else False,
        "store_size": len(vault._store),
        "shredded_size": len(vault._shredded),
    }

PII_patterns = {
    "PHONE": re.compile(r"\+?\d[d\-s]{7,}\d"),
    "ACCOUNT": re.compile(r"\b\d{4,12}\b"),
    "EMAIL": re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"),
}


def reload_vault() -> bool:
    if not HAS_VAULT or vault is None or vault.path is None:
        return False
    if not Path(vault.path).exists():
        return False
    try:
        vault._load()
        return True
    except Exception:
        return False


def make_sensitive_text(text: str, mask_pii: bool = True) -> Tuple[str, List[Dict]]:
    """Mask PII using vault for deterministic tokens."""
    if not mask_pii:
        return text, []

    masked_spans = []
    masked_text = text

    for label, pattern in PII_patterns.items():
        for match in pattern.finditer(text):  # Use original text for matching positions
            span_text = match.group(0)
            
            # Use vault for deterministic tokens if available
            if HAS_VAULT and vault:
                finding = Finding(
                    label,
                    span_text,
                    start=match.start(),
                    end=match.end(),
                    confidence=1.0,
                    source="regex",
                )
                token = vault.token_for(finding)
            else:
                # Fallback to sequential token if vault unavailable
                token = f"{label}_{len(masked_spans) + 1:03d}"
            
            masked_text = masked_text.replace(span_text, token, 1)
            masked_spans.append({
                "token": token,
                "label": label,
                "original": span_text,
            })

    return masked_text, masked_spans



def detokenize_text(text:str, masked_spans: List[Dict]) -> str:
    detokenized = text
    for span in masked_spans:
        detokenized = detokenized.replace(span["token"], span["original"])
    return detokenized

