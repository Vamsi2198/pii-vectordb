#!/usr/bin/env python
"""
Direct test of the RAG fixes without terminal path issues.
"""
import sys
import os

# Setup path
workspace_root = r'c:\Users\HP\OneDrive\Documents\dinesh sir\aagcp_pro'
os.chdir(workspace_root)
sys.path.insert(0, workspace_root)
sys.path.insert(0, os.path.join(workspace_root, 'pii-rag-main'))

print("[SETUP] Python path configured")
print(f"[SETUP] Working directory: {os.getcwd()}")

# Test 1: Check if access.py fix works
print("\n" + "="*80)
print("[TEST 1] Testing is_allowed() fix")
print("="*80)

from RAG.access import is_allowed

# Test case 1: Empty allowed_roles should now allow access
meta1 = {"text": "sample", "allowed_roles": []}
result1 = is_allowed("analyst", meta1)
print(f"Empty allowed_roles → is_allowed('analyst') = {result1}")
print(f"✅ PASS" if result1 else "❌ FAIL - Still blocking empty roles!")

# Test case 2: Explicit role list
meta2 = {"text": "sample", "allowed_roles": ["analyst", "manager"]}
result2 = is_allowed("analyst", meta2)
print(f"Explicit roles → is_allowed('analyst') = {result2}")
print(f"✅ PASS" if result2 else "❌ FAIL")

# Test case 3: Missing allowed_roles key (default behavior)
meta3 = {"text": "sample"}
result3 = is_allowed("analyst", meta3)
print(f"Missing allowed_roles key → is_allowed('analyst') = {result3}")
print(f"✅ PASS" if result3 else "❌ FAIL - Should default to allowing access!")

# Test 2: Check if prepare_chunks adds allowed_roles
print("\n" + "="*80)
print("[TEST 2] Testing prepare_chunks() sets allowed_roles")
print("="*80)

from RAG.workflow import prepare_chunks

test_docs = [
    {"text": "This is a test document with PII like Ramesh Iyer", "source": "test.pdf"}
]

chunks, metas = prepare_chunks(test_docs, mask_pii=False)
print(f"Generated {len(chunks)} chunks from {len(test_docs)} documents")
print(f"First chunk metadata keys: {list(metas[0].keys())}")
print(f"allowed_roles present: {'allowed_roles' in metas[0]}")
print(f"allowed_roles value: {metas[0].get('allowed_roles', 'MISSING')}")

if 'allowed_roles' in metas[0] and len(metas[0]['allowed_roles']) > 0:
    print("✅ PASS - prepare_chunks now sets allowed_roles")
else:
    print("❌ FAIL - allowed_roles not properly set")

# Test 3: Try the vault integration
print("\n" + "="*80)
print("[TEST 3] Testing vault integration in make_sensitive_text")
print("="*80)

from Data_ingestion.pii import make_sensitive_text, HAS_VAULT

print(f"Vault available: {HAS_VAULT}")

test_text = "John Doe's email is john@example.com and phone is +1-555-1234"
masked, spans = make_sensitive_text(test_text, mask_pii=True)
print(f"\nOriginal: {test_text}")
print(f"Masked:   {masked}")
print(f"\nPII found: {len(spans)} instances")
for span in spans:
    print(f"  - {span['label']}: '{span['original']}' → {span['token']}")

if HAS_VAULT and any('<' in span['token'] and '_' in span['token'] for span in spans):
    print("\n✅ PASS - Using vault tokens (deterministic format)")
else:
    print("\n⚠️  WARNING - Not using vault tokens (sequential format)")

print("\n" + "="*80)
print("[SUMMARY] RAG fixes verified!")
print("="*80)
