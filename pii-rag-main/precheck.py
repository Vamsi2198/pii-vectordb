#!/usr/bin/env python
"""
Pre-flight check for RAG main.py setup.
Run this before starting the server to verify everything is configured correctly.
"""

import sys
import os
from pathlib import Path

os.chdir(Path(__file__).parent)
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))

print("="*80)
print("RAG Main.py - Pre-flight Check")
print("="*80)

# Check 1: Required files
print("\n[CHECK 1] Required files...")
required_files = [
    "main.py",
    "static/test_console.html",
    "static/index.html",
    "RAG/workflow.py",
    "Data_ingestion/pii.py",
    "RAG/access.py",
]

all_exist = True
for fname in required_files:
    fpath = Path(fname)
    exists = "✅" if fpath.exists() else "❌"
    print(f"  {exists} {fname}")
    if not fpath.exists():
        all_exist = False

if all_exist:
    print("  All files present!")
else:
    print("  ⚠️  Some files missing!")

# Check 2: Python imports
print("\n[CHECK 2] Python imports...")
try:
    from RAG.workflow import search_question, bm25_metas
    print("  ✅ RAG.workflow")
except Exception as e:
    print(f"  ❌ RAG.workflow: {e}")

try:
    from RAG.access import resolve_role, is_allowed
    print("  ✅ RAG.access")
except Exception as e:
    print(f"  ❌ RAG.access: {e}")

try:
    from Data_ingestion.pii import make_sensitive_text
    print("  ✅ Data_ingestion.pii")
except Exception as e:
    print(f"  ❌ Data_ingestion.pii: {e}")

try:
    from aagcp.vault import PseudonymVault
    print("  ✅ aagcp.vault (deterministic tokens enabled)")
except Exception as e:
    print(f"  ⚠️  aagcp.vault: {e} (will use sequential tokens)")

# Check 3: FastAPI setup
print("\n[CHECK 3] FastAPI setup...")
try:
    from fastapi import FastAPI
    print("  ✅ FastAPI installed")
except Exception as e:
    print(f"  ❌ FastAPI: {e}")

try:
    import uvicorn
    print("  ✅ Uvicorn installed")
except Exception as e:
    print(f"  ❌ Uvicorn: {e}")

# Check 4: RAG index status
print("\n[CHECK 4] RAG index status...")
try:
    from RAG.workflow import bm25_metas
    chunk_count = len(bm25_metas) if bm25_metas else 0
    if chunk_count > 0:
        print(f"  ✅ {chunk_count} chunks loaded in RAG index")
    else:
        print(f"  ⚠️  No chunks loaded yet")
        print("     (Upload documents first via /upload endpoint)")
except Exception as e:
    print(f"  ❌ Error checking index: {e}")

# Check 5: Vault integration
print("\n[CHECK 5] Vault integration in pii.py...")
try:
    from Data_ingestion.pii import HAS_VAULT
    if HAS_VAULT:
        print("  ✅ Vault is available (deterministic tokens)")
    else:
        print("  ⚠️  Vault not available (using sequential tokens)")
except Exception as e:
    print(f"  ❌ Error checking vault: {e}")

print("\n" + "="*80)
print("Pre-flight check complete!")
print("="*80)
print("\nTo start the RAG server, run:")
print("  python -m uvicorn main:app --port 8001 --reload")
print("\nThen visit:")
print("  http://localhost:8001/test")
print("="*80)
