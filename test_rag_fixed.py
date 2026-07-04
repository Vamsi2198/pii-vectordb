#!/usr/bin/env python
"""Test RAG workflow - check if chunks are now returned."""

import sys
import os

# Change to workspace directory
os.chdir(r'c:\Users\HP\OneDrive\Documents\dinesh sir\aagcp_pro')
sys.path.insert(0, 'pii-rag-main')

from RAG.workflow import search_question, bm25_metas

question = 'who came to Apollo Hospital for diabetes checkup'
print(f'[TEST] Query: {question}')
print('='*80)
print(f'[DEBUG] Total chunks in index: {len(bm25_metas)}')

if len(bm25_metas) == 0:
    print("❌ NO DATA INGESTED! Index is empty.")
    print("   You need to run ingest_file() first to load PDFs.")
else:
    print(f"✅ Index has {len(bm25_metas)} chunks")
    
try:
    results = search_question(question, role='ANALYST_PARTIAL', top_k=5)
    print(f'\n[RESULTS] Chunks returned: {len(results)}')
    
    if len(results) == 0:
        print("❌ STILL NO CHUNKS!")
    else:
        for i, result in enumerate(results[:3]):
            print(f'\n--- Result {i+1} ---')
            score = result.get("score", "N/A")
            meta = result.get('meta', {})
            text = meta.get("text", "NO TEXT")
            print(f'Score: {score}')
            print(f'Text: {text[:200]}...')
            
except Exception as e:
    print(f'❌ ERROR: {type(e).__name__}: {e}')
    import traceback
    traceback.print_exc()
