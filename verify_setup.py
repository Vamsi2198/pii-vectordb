#!/usr/bin/env python3
"""
Quick verification that AAGCP + Pinecone app setup is valid.
Run before launching the actual app.
"""

import sys
import os

def check_imports():
    """Check all required imports work."""
    print("=" * 60)
    print("CHECKING IMPORTS")
    print("=" * 60)
    
    checks = [
        ("FastAPI", lambda: __import__('fastapi')),
        ("Uvicorn", lambda: __import__('uvicorn')),
        ("Pinecone", lambda: __import__('pinecone')),
        ("SentenceTransformers", lambda: __import__('sentence_transformers')),
        ("NumPy", lambda: __import__('numpy')),
        ("dotenv", lambda: __import__('dotenv')),
        ("AAGCP.detect", lambda: __import__('aagcp.detect.detector')),
        ("AAGCP.embed", lambda: __import__('aagcp.embed.embedders')),
        ("AAGCP.store", lambda: __import__('aagcp.store.connectors')),
        ("AAGCP.vault", lambda: __import__('aagcp.vault')),
        ("AAGCP.scan", lambda: __import__('aagcp.scan.scanner')),
        ("AAGCP.migrate", lambda: __import__('aagcp.migrate.migrator')),
    ]
    
    failed = []
    for name, loader in checks:
        try:
            loader()
            print(f"✓ {name}")
        except ImportError as e:
            print(f"✗ {name}: {e}")
            failed.append(name)
    
    return len(failed) == 0

def check_env():
    """Check environment variables."""
    print("\n" + "=" * 60)
    print("CHECKING ENVIRONMENT")
    print("=" * 60)
    
    from dotenv import load_dotenv
    load_dotenv()
    
    api_key = os.getenv("PINECONE_API_KEY") or os.getenv("pinecode_key")
    if api_key:
        print(f"✓ PINECONE_API_KEY found ({len(api_key)} chars)")
    else:
        print("✗ PINECONE_API_KEY not set")
        return False
    
    vault_secret = os.getenv("VAULT_SECRET")
    if vault_secret:
        print(f"✓ VAULT_SECRET found")
    else:
        print("⚠ VAULT_SECRET not set (using default)")
    
    return True

def check_aagcp_modules():
    """Test AAGCP module loading."""
    print("\n" + "=" * 60)
    print("CHECKING AAGCP MODULES")
    print("=" * 60)
    
    try:
        from aagcp.detect.detector import PIIDetector
        detector = PIIDetector()
        print(f"✓ PIIDetector initialized: {detector.coverage()}")
    except Exception as e:
        print(f"✗ PIIDetector: {e}")
        return False
    
    try:
        from aagcp.embed.embedders import SentenceTransformerEmbedder
        embedder = SentenceTransformerEmbedder("all-MiniLM-L6-v2")
        print(f"✓ SentenceTransformerEmbedder loaded: {embedder.dim}D")
    except Exception as e:
        print(f"✗ SentenceTransformerEmbedder: {e}")
        return False
    
    try:
        from aagcp.vault import PseudonymVault
        vault = PseudonymVault()
        print(f"✓ PseudonymVault initialized")
    except Exception as e:
        print(f"✗ PseudonymVault: {e}")
        return False
    
    try:
        from aagcp.store.connectors import VectorRecord
        rec = VectorRecord(id="test", vector=None, source_text="test")
        print(f"✓ VectorRecord created")
    except Exception as e:
        print(f"✗ VectorRecord: {e}")
        return False
    
    return True

def check_pinecone():
    """Test Pinecone connection."""
    print("\n" + "=" * 60)
    print("CHECKING PINECONE")
    print("=" * 60)
    
    from dotenv import load_dotenv
    load_dotenv()
    
    try:
        from pinecone import Pinecone
        api_key = os.getenv("PINECONE_API_KEY") or os.getenv("pinecode_key")
        pc = Pinecone(api_key=api_key)
        
        indexes = pc.list_indexes()
        print(f"✓ Connected to Pinecone")
        print(f"  Available indexes: {indexes}")
        
        # Try to find 384D index
        target_dim = 384
        for idx_name in indexes:
            try:
                desc = pc.describe_index(idx_name)
                dim = getattr(desc, "dimension", None)
                status = getattr(desc, "status", None)
                print(f"  - {idx_name}: {dim}D, status={status}")
                
                if dim == target_dim:
                    print(f"  ✓ Found compatible {target_dim}D index: {idx_name}")
                    return True
            except Exception:
                pass
        
        print(f"⚠ No {target_dim}D index found (may need to create or adjust)")
        return True
    
    except Exception as e:
        print(f"✗ Pinecone connection failed: {e}")
        return False

def main():
    """Run all checks."""
    print("\n")
    print("╔" + "═" * 58 + "╗")
    print("║" + " " * 10 + "AAGCP + PINECONE APP SETUP CHECK" + " " * 16 + "║")
    print("╚" + "═" * 58 + "╝\n")
    
    results = []
    results.append(("Imports", check_imports()))
    results.append(("Environment", check_env()))
    results.append(("AAGCP Modules", check_aagcp_modules()))
    results.append(("Pinecone", check_pinecone()))
    
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    
    for name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{name:.<40} {status}")
    
    all_passed = all(p for _, p in results)
    
    if all_passed:
        print("\n✓ All checks passed! App is ready to run:")
        print("\n  python app_aagcp_pinecone.py")
        print("\n  Then visit: http://localhost:8001")
        return 0
    else:
        print("\n✗ Some checks failed. Fix issues above and retry.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
