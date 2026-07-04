#!/usr/bin/env python
"""
Test script to run RAG main.py and test the query endpoint.
"""
import subprocess
import time
import sys
import requests
import json
import os

# Setup paths
workspace_root = r'c:\Users\HP\OneDrive\Documents\dinesh sir\aagcp_pro'
rag_dir = os.path.join(workspace_root, 'pii-rag-main')

print("="*80)
print("[SETUP] Starting RAG server test")
print("="*80)
print(f"Workspace: {workspace_root}")
print(f"RAG dir: {rag_dir}")

# Change to RAG directory
os.chdir(rag_dir)
print(f"Current dir: {os.getcwd()}")

# Test 1: Check if we can import the modules
print("\n[TEST 1] Checking imports...")
try:
    sys.path.insert(0, workspace_root)
    sys.path.insert(0, rag_dir)
    from RAG.workflow import search_question
    from RAG.access import resolve_role
    print("✅ RAG modules imported successfully")
except Exception as e:
    print(f"❌ Import error: {e}")
    sys.exit(1)

# Test 2: Check bm25 index
print("\n[TEST 2] Checking if data is in index...")
try:
    from RAG.workflow import bm25_metas
    print(f"Chunks in index: {len(bm25_metas) if bm25_metas else 0}")
    if len(bm25_metas) == 0:
        print("⚠️  Index is EMPTY - no documents ingested yet")
        print("   To add data, use: ingest_file('path/to/document.pdf')")
    else:
        print(f"✅ Index has {len(bm25_metas)} chunks")
except Exception as e:
    print(f"❌ Error checking index: {e}")

# Test 3: Direct query test (no server needed)
print("\n[TEST 3] Testing search_question() directly...")
try:
    question = "who came to Apollo Hospital for diabetes checkup"
    print(f"Query: {question}")
    
    results = search_question(question, role='ANALYST_PARTIAL', top_k=3)
    print(f"✅ Got {len(results)} results from search_question()")
    
    if len(results) == 0:
        print("⚠️  No results returned")
        print("    This is expected if index is empty")
    else:
        for i, result in enumerate(results[:2]):
            score = result.get('score', 0)
            meta = result.get('meta', {})
            text = meta.get('text', 'NO TEXT')[:100]
            print(f"\n  Result {i+1}:")
            print(f"    Score: {score:.4f}")
            print(f"    Text: {text}...")
            
except Exception as e:
    print(f"❌ Query error: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "="*80)
print("[NEXT STEP]")
print("="*80)
print("To start the RAG server, run:")
print(f'  cd "{rag_dir}"')
print("  python -m uvicorn main:app --port 8001")
print("\nThen test the query endpoint:")
print('  http://localhost:8001/query?question=who%20came%20to%20Apollo%20Hospital&authorization=analyst_token')
print("="*80)
