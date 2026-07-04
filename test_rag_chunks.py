#!/usr/bin/env python
"""Test RAG workflow to debug why chunks are not being returned."""

import sys
sys.path.insert(0, 'pii-rag-main')

from RAG.workflow import search_question

# Test query
question = 'who came to Apollo Hospital for diabetes checkup'
print(f'Testing query: {question}')
print('='*80)

try:
    print("\n[1] Calling search_question with ANALYST_PARTIAL role...")
    results = search_question(question, role='ANALYST_PARTIAL', top_k=5)
    
    print(f'\n[2] Results returned: {len(results)}')
    
    if len(results) == 0:
        print("❌ NO CHUNKS RETURNED! This is the problem.")
    else:
        for i, result in enumerate(results):
            print(f'\n--- Result {i+1} ---')
            print(f'Score: {result.get("score", "N/A")}')
            meta = result.get('meta', {})
            text = meta.get("text", "NO TEXT")
            print(f'Text length: {len(text)} chars')
            print(f'Text preview: {text[:300]}...')
            print(f'Source: {meta.get("source", "N/A")}')
            print(f'All keys: {list(meta.keys())}')
            
except Exception as e:
    print(f'❌ ERROR: {type(e).__name__}: {e}')
    import traceback
    traceback.print_exc()
