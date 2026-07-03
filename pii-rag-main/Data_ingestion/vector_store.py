import os
import pickle
from typing import List, Dict
from dotenv import load_dotenv

load_dotenv()

import numpy as np


class PineconeIndex:
    """Pinecone-backed index wrapper.

    Requires the `pinecone-client` package and the environment variable
    `PINECONE_API_KEY` (legacy key `pinecode_key` is also accepted).
    """
    def __init__(self, dim: int, index_name: str = None, namespace: str = ""):
        try:
            import pinecone
        except Exception as e:
            raise RuntimeError("pinecone package is required to use PineconeIndex") from e

        api_key = os.getenv("PINECONE_API_KEY") or os.getenv("pinecode_key")
        if not api_key:
            raise RuntimeError("PINECONE_API_KEY (or pinecode_key) environment variable is required")

        # record expected dimension
        self.dim = int(dim)

        # Initialize Pinecone client (supporting new and legacy SDKs)
        pinecone_env = os.getenv("PINECONE_ENVIRONMENT")

        import pinecone as _pine_mod

        # prefer new-style API when available
        if hasattr(_pine_mod, "Pinecone"):
            from pinecone import Pinecone
            pc = Pinecone(api_key=api_key, environment=pinecone_env) if pinecone_env else Pinecone(api_key=api_key)

            self.index_name = index_name or os.getenv("PINECONE_INDEX", "ragpii")
            self.namespace = namespace

            # try to obtain the index client; if not present, create it
            try:
                self._pine = pc.index(self.index_name)
            except Exception as e:
                msg = str(e).lower()
                if "notfound" in msg or "not found" in msg or "404" in msg:
                    try:
                        from pinecone import ServerlessSpec
                        pc.create_index(
                            name=self.index_name,
                            dimension=dim,
                            metric="cosine",
                            spec=ServerlessSpec(cloud="aws", region="us-east-1")
                        )
                    except Exception as create_err:
                        print(f"Warning: Could not create index {self.index_name}: {create_err}")
                    self._pine = pc.index(self.index_name)
                else:
                    raise

            # CRITICAL: check remote dimension and handle mismatch by finding compatible index
            remote_dim = None
            compatible_index = None
            
            try:
                if hasattr(pc, "describe_index"):
                    desc = pc.describe_index(self.index_name)
                    # IndexModel object has .dimension attribute
                    remote_dim = getattr(desc, "dimension", None)
                    if remote_dim is None and isinstance(desc, dict):
                        remote_dim = desc.get("dimension")
            except Exception as e:
                print(f"Warning: Could not describe index {self.index_name}: {e}")
                remote_dim = None

            # If remote dimension exists and doesn't match, look for an existing compatible index
            if remote_dim is not None:
                try:
                    remote_dim = int(remote_dim)
                except Exception:
                    remote_dim = None

                if remote_dim is not None and remote_dim != dim:
                    print(f"Dimension mismatch: index {self.index_name} is {remote_dim}D but embedding is {dim}D.")
                    
                    # Look for an existing index with matching dimension
                    print(f"Searching for existing {dim}D index...")
                    for idx_name in pc.list_indexes():
                        try:
                            idx_desc = pc.describe_index(idx_name)
                            idx_dim = getattr(idx_desc, "dimension", None)
                            if idx_dim == dim:
                                print(f"Found compatible index: {idx_name} ({dim}D). Using that instead.")
                                compatible_index = idx_name
                                break
                        except Exception:
                            continue
                    
                    if compatible_index:
                        self.index_name = compatible_index
                        self._pine = pc.index(self.index_name)
                    else:
                        print(f"No compatible {dim}D index found. Attempting to create {self.index_name}-{dim}...")
                        new_name = f"{self.index_name}-{dim}"
                        try:
                            from pinecone import ServerlessSpec
                            pc.create_index(
                                name=new_name,
                                dimension=dim,
                                metric="cosine",
                                spec=ServerlessSpec(cloud="aws", region="us-east-1")
                            )
                            self.index_name = new_name
                            self._pine = pc.index(self.index_name)
                        except Exception as e:
                            print(f"Cannot create new index (tier limit?): {e}")
                            print(f"Please either: 1) delete an unused index, 2) set PINECONE_INDEX env var to a {dim}D index, or 3) upgrade your Pinecone plan.")
                            raise RuntimeError(f"No compatible {dim}D index available and cannot create new one. {e}")

        elif hasattr(_pine_mod, "init"):
            # legacy-style API
            if pinecone_env:
                try:
                    _pine_mod.init(api_key=api_key, environment=pinecone_env)
                except Exception:
                    _pine_mod.init(api_key=api_key)
            else:
                _pine_mod.init(api_key=api_key)

            self.index_name = index_name or os.getenv("PINECONE_INDEX", "ragpii")
            self.namespace = namespace

            # attempt to detect existing index dimension
            try:
                remote_dim = None
                if hasattr(_pine_mod, "describe_index"):
                    desc = _pine_mod.describe_index(self.index_name)
                    remote_dim = desc.get("dimension") if isinstance(desc, dict) else getattr(desc, "dimension", None)
                if remote_dim is not None and int(remote_dim) != dim:
                    new_name = f"{self.index_name}-{dim}"
                    try:
                        _pine_mod.create_index(new_name, dimension=dim, metric="cosine")
                        self.index_name = new_name
                    except Exception:
                        pass
                else:
                    try:
                        if self.index_name not in _pine_mod.list_indexes():
                            _pine_mod.create_index(self.index_name, dimension=dim, metric="cosine")
                    except Exception:
                        pass
            except Exception:
                pass

            # obtain client
            try:
                self._pine = _pine_mod.Index(self.index_name)
            except TypeError:
                self._pine = _pine_mod.index(self.index_name)

        else:
            raise RuntimeError("Installed pinecone package is not compatible; please install the official 'pinecone' SDK.")

    def add(self, vectors: np.ndarray, metas: List[Dict]):
        # vectors: ndarray (N, D)
        # quick validation: ensure vector dimensionality matches the index
        try:
            first_vec = vectors[0]
        except Exception:
            raise ValueError("No vectors provided to add()")

        vec_len = first_vec.shape[0] if hasattr(first_vec, "shape") else len(first_vec)
        if vec_len != self.dim:
            raise RuntimeError(f"Vector dimension {vec_len} does not match index dimension {self.dim}")
        to_upsert = []
        import uuid
        for i, vec in enumerate(vectors):
            vid = metas[i].get("id") if isinstance(metas[i], dict) else None
            if not vid:
                vid = uuid.uuid4().hex
            md = dict(metas[i]) if isinstance(metas[i], dict) else {}
            to_upsert.append((vid, vec.tolist(), md))

        # upsert in batches
        batch_size = 100
        for i in range(0, len(to_upsert), batch_size):
            chunk = to_upsert[i:i+batch_size]
            self._pine.upsert(vectors=chunk, namespace=self.namespace)

    def search(self, query_vector, k: int = 5):
        # query_vector: ndarray (1, D) or list
        q = query_vector[0].tolist() if hasattr(query_vector, "shape") else list(query_vector)
        res = self._pine.query(vector=q, top_k=k, include_metadata=True, namespace=self.namespace)
        results = []
        matches = res.get("matches", []) if isinstance(res, dict) else getattr(res, "matches", [])
        row = []
        for m in matches:
            score = float(m.get("score", m.get("similarity", 0.0)))
            meta = m.get("metadata", {})
            row.append({"score": score, "meta": meta})
        results.append(row)
        return results

    def save(self, path_index, path_meta):
        # Pinecone is remote; write a small metadata stub locally
        with open(path_meta, "wb") as f:
            pickle.dump({"index_name": self.index_name, "namespace": self.namespace}, f)

    def load(self, path_index, path_meta):
        # No local load for Pinecone; keep as no-op
        pass