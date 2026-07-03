#!/usr/bin/env python
import os
from dotenv import load_dotenv
from pinecone import Pinecone

load_dotenv()

api_key = os.environ.get("PINECONE_API_KEY")
if not api_key:
    print("Error: PINECONE_API_KEY not set. Check .env file or set it manually.")
    exit(1)

pc = Pinecone(api_key=api_key)
print("Indexes in Pinecone:")
for name in pc.list_indexes():
    try:
        desc = pc.describe_index(name)
        dim = desc.get("dimension") if isinstance(desc, dict) else getattr(desc, "dimension", None)
    except Exception as e:
        dim = f"Error: {e}"
    print(f"  {name} dim={dim}")
