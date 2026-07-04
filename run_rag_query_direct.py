#!/usr/bin/env python
import sys
import os
sys.path.insert(0, r'c:\Users\HP\OneDrive\Documents\dinesh sir\aagcp_pro')
sys.path.insert(0, r'c:\Users\HP\OneDrive\Documents\dinesh sir\aagcp_pro\pii-rag-main')
os.chdir(r'c:\Users\HP\OneDrive\Documents\dinesh sir\aagcp_pro\pii-rag-main')

# Test the query
from RAG.workflow import search_question, bm25_metas
from RAG.access import resolve_role

print("="*80)
print("RAG QUERY TEST")
print("="*80)
print(f"\n[INFO] Chunks in index: {len(bm25_metas) if bm25_metas else 0}")

if len(bm25_metas) == 0:
    print("❌ No data in index!")
    print("   Index is empty - need to ingest documents first")
else:
    question = "who came to Apollo Hospital for diabetes checkup"
    print(f"\n[QUERY] {question}")
    print("-" * 80)
    
    try:
        # Test with ANALYST role
        results = search_question(question, role='ANALYST_PARTIAL', top_k=5)
        print(f"\n✅ ANALYST_PARTIAL role - {len(results)} results:")
        
        for i, result in enumerate(results[:3], 1):
            print(f"\n  [{i}] Score: {result['score']:.4f}")
            meta = result['meta']
            text = meta.get('text', 'NO TEXT')
            print(f"      Text: {text[:150]}...")
            print(f"      Source: {meta.get('source', 'N/A')}")
        
        # Test with COMPLIANCE role
        results_compliance = search_question(question, role='COMPLIANCE', top_k=5)
        print(f"\n✅ COMPLIANCE role - {len(results_compliance)} results (should show full reveal)")
        
        if results_compliance:
            meta = results_compliance[0]['meta']
            text = meta.get('text', 'NO TEXT')
            print(f"   First result text: {text[:150]}...")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

print("\n" + "="*80)
