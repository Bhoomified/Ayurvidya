"""Embedding models behind one small interface.

  tfidf            character n-gram TF-IDF (scikit-learn). Offline, no download, strong on exact Sanskrit
                   word forms. Used for tests and as a baseline in the retrieval experiment.
  st:<model>       any sentence-transformers model, e.g.
                   st:BAAI/bge-m3                     (568M, 100+ languages, 8192 tokens)
                   st:Qwen/Qwen3-Embedding-0.6B       (instruction-aware; best MMTEB score at its size)
                   st:intfloat/multilingual-e5-large-instruct

All embedders return L2-normalised float32 rows, so cosine similarity == dot product.
"""
from __future__ import annotations

import pickle
from pathlib import Path
from typing import Protocol

import numpy as np

from .text import fold_for_search, normalize


class Embedder(Protocol):
    name: str
    def fit(self, texts: list[str]) -> None: ...
    def embed_documents(self, texts: list[str]) -> np.ndarray: ...
    def embed_query(self, text: str) -> np.ndarray: ...
    def save(self, path: Path) -> None: ...


def _l2(m: np.ndarray) -> np.ndarray:
    m = np.asarray(m, dtype=np.float32)
    n = np.linalg.norm(m, axis=1, keepdims=True)
    n[n == 0] = 1.0
    return m / n


def _dual_script(text: str) -> str:
    """Index text in Devanagari AND folded Roman so a query in either script matches."""
    t = normalize(text)
    return t + " \n " + fold_for_search(t)


class TfidfEmbedder:
    name = "tfidf"

    def __init__(self, ngram_range=(2, 4), max_features: int = 200_000):
        from sklearn.feature_extraction.text import TfidfVectorizer
        self.vec = TfidfVectorizer(analyzer="char_wb", ngram_range=ngram_range,
                                   max_features=max_features, sublinear_tf=True)
        self._fitted = False

    def fit(self, texts: list[str]) -> None:
        self.vec.fit([_dual_script(t) for t in texts])
        self._fitted = True

    def embed_documents(self, texts: list[str]):
        """Returns a SPARSE L2-normalised matrix (scipy CSR): 25k+ dimensions but few non-zeros,
        so 5,000 chunks take a few MB instead of hundreds."""
        if not self._fitted:
            raise RuntimeError("TfidfEmbedder.fit() must be called on the corpus first")
        from sklearn.preprocessing import normalize as sk_normalize
        return sk_normalize(self.vec.transform([_dual_script(t) for t in texts])).astype(np.float32)

    def embed_query(self, text: str) -> np.ndarray:
        return np.asarray(self.embed_documents([text]).toarray()[0], dtype=np.float32)

    def save(self, path: Path) -> None:
        Path(path).write_bytes(pickle.dumps(self.vec))

    @classmethod
    def load(cls, path: Path) -> "TfidfEmbedder":
        e = cls()
        e.vec = pickle.loads(Path(path).read_bytes())
        e._fitted = True
        return e


class SentenceTransformerEmbedder:
    """Dense multilingual embeddings. Model-specific query/passage prefixes are applied automatically."""

    def __init__(self, model_name: str, device: str | None = None, batch_size: int = 16):
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as e:  # pragma: no cover - depends on optional install
            raise ImportError("pip install sentence-transformers  (needed for st:<model> embedders)") from e
        self.name = f"st:{model_name}"
        self.model = SentenceTransformer(model_name, device=device)
        self.batch_size = batch_size
        low = model_name.lower()
        self.q_prefix, self.d_prefix, self.q_prompt_name = "", "", None
        if "e5" in low and "instruct" in low:
            self.q_prefix = ("Instruct: Given a question about a Sanskrit Ayurveda verse, "
                             "retrieve passages that answer it\nQuery: ")
        elif "e5" in low:
            self.q_prefix, self.d_prefix = "query: ", "passage: "
        elif "qwen3-embedding" in low:
            self.q_prompt_name = "query"

    def fit(self, texts: list[str]) -> None:  # pre-trained: nothing to fit
        return None

    def embed_documents(self, texts: list[str]) -> np.ndarray:
        return _l2(self.model.encode([self.d_prefix + normalize(t) for t in texts],
                                     batch_size=self.batch_size, normalize_embeddings=True,
                                     show_progress_bar=len(texts) > 200))

    def embed_query(self, text: str) -> np.ndarray:
        kw = {"prompt_name": self.q_prompt_name} if self.q_prompt_name else {}
        return _l2(self.model.encode([self.q_prefix + text], normalize_embeddings=True, **kw))[0]

    def save(self, path: Path) -> None:
        Path(path).write_text(self.name, encoding="utf-8")


def make_embedder(spec: str) -> Embedder:
    if spec == "tfidf":
        return TfidfEmbedder()
    if spec.startswith("st:"):
        return SentenceTransformerEmbedder(spec[3:])
    raise ValueError(f"Unknown embedder spec '{spec}' (use 'tfidf' or 'st:<model>')")


def load_embedder(spec: str, kb_dir: Path) -> Embedder:
    if spec == "tfidf":
        return TfidfEmbedder.load(Path(kb_dir) / "tfidf.pkl")
    return make_embedder(spec)
