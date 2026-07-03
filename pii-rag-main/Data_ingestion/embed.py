from typing import List
import numpy as np

def embed_texts(texts: List[str], model):
    return np.vstack([model.encode(t) for t in texts])