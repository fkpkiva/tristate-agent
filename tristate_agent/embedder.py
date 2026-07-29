from __future__ import annotations
import math, re
from typing import List, Optional

__all__ = ["embed","cosine_similarity","OllamaEmbedder","OpenAIEmbedder","NullEmbedder","make_embedder"]

_DIM = 512
_VOCAB: dict = {}

def _tok(t):
    return re.findall(r"[a-z0-9]+", t.lower())

def _bow(text):
    tokens = _tok(text)
    vec = [0.0]*_DIM
    for t in tokens:
        if t not in _VOCAB: _VOCAB[t] = len(_VOCAB) % _DIM
        vec[_VOCAB[t]] += 1.0
    n = math.sqrt(sum(v*v for v in vec)) or 1.0
    return [v/n for v in vec]

def embed(text: str) -> List[float]:
    return _bow(text)

def cosine_similarity(a,b):
    d=sum(x*y for x,y in zip(a,b))
    na=math.sqrt(sum(x*x for x in a))
    nb=math.sqrt(sum(y*y for y in b))
    return 0. if na==0. or nb==0. else d/(na*nb)

class NullEmbedder:
    def embed(self, text):
        return []
    def __call__(self, text):
        return self.embed(text)
    def similarity(self, a, b):
        return cosine_similarity(a, b)

class OllamaEmbedder:
    def __init__(self, model="nomic-embed-text", base_url="http://localhost:11434"):
        self.model = model; self.base_url = base_url
    def embed(self, text: str) -> List[float]:
        try:
            import requests
            r = requests.post(f"{self.base_url}/api/embeddings", json={"model": self.model, "prompt": text}, timeout=10)
            return r.json()["embedding"]
        except Exception:
            return []
    def __call__(self, text):
        return self.embed(text)
    def similarity(self, a, b):
        return cosine_similarity(a, b)

class OpenAIEmbedder:
    def __init__(self, model="text-embedding-3-small", api_key: Optional[str] = None):
        self.model = model; self.api_key = api_key
    def embed(self, text: str) -> List[float]:
        try:
            import openai
            client = openai.OpenAI(api_key=self.api_key)
            return client.embeddings.create(input=text, model=self.model).data[0].embedding
        except Exception:
            return []
    def __call__(self, text):
        return self.embed(text)
    def similarity(self, a, b):
        return cosine_similarity(a, b)

def make_embedder(backend: str = "null", **kwargs):
    if backend == "ollama": return OllamaEmbedder(**kwargs)
    if backend == "openai": return OpenAIEmbedder(**kwargs)
    return NullEmbedder()
