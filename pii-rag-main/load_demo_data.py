#!/usr/bin/env python
"""
Quick way to test RAG queries - instructions and verification.
"""

import sys
import os
from pathlib import Path

os.chdir(Path(__file__).parent)
sys.path.insert(0, str(Path(__file__).parent))

print("="*80)
print("RAG Chunks Test Verification")
print("="*80)

# Check current state
from RAG.workflow import bm25_metas

print(f"\n[STATUS] Current RAG index chunks: {len(bm25_metas) if bm25_metas else 0}")

if len(bm25_metas) == 0:
    print("\n❌ No chunks in RAG index!")
    print("\nTo test chunks, you need to:")
    print("\n1. OPTION A: Upload via RAG test console")
    print("   - Visit: http://localhost:8001/test")
    print("   - Look for upload button (if available)")
    print("")
    print("2. OPTION B: Use the /upload endpoint")
    print("   - POST http://localhost:8001/upload")
    print("   - Form data: file (PDF/DOCX/TXT)")
    print("")
    print("3. OPTION C: Create a sample document file and upload")
    print("   - Create: sample_medical.txt with patient data")
    print("   - Upload via curl:")
    print("   curl -F 'file=@sample_medical.txt' http://localhost:8001/upload")
    print("")
else:
    print(f"\n✅ RAG index has {len(bm25_metas)} chunks loaded!")
    print("   Queries should now return results")
    print("")
    print("Test it:")
    print("   http://localhost:8001/test")
    print("")
    print("Sample query: 'who came to Apollo Hospital for diabetes checkup'")

print("\n" + "="*80)
print("Quick Test: Sample Medical Document")
print("="*80)

print("\nCreate this file as: uploads/sample.txt")
print("-" * 80)
print("""Patient Medical History Report

On 2023-11-15, Ramesh Iyer, a 51-year-old patient from Mumbai, India, visited Apollo Hospital for his routine diabetes checkup. His Aadhaar number is 234567890123 and his phone number is +91-9876543210.

Medical Summary:
The patient has been a diabetic for 5 years. Current medications include Metformin 500mg twice daily. His recent HbA1c levels were 7.2%.

Diagnosis: Type 2 Diabetes - Well controlled
Status: Routine follow-up completed
Contact: ramesh.iyer@email.com
""")
print("-" * 80)

print("\nThen upload via: POST /upload with file=sample.txt")
print("="*80)
