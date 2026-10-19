"""Hybrid retrieval = dense (meaning) + BM25 (exact Sanskrit forms), fused with Reciprocal Rank Fusion,
then an optional cross-encoder reranker.

    RRF(d) = sum over retrievers r of 1 / (k + rank_r(d)),  k = 60   (Cormack, Clarke & Buettcher, 2009)

RRF uses ranks, not raw scores, so cosine similarities and BM25 scores never have to be put on one scale.
"""
from __future__ import annotations

from dataclasses import dataclass

from .index import KnowledgeBase, bm25_tokens
from .schema import Chunk, Hit
from .text import to_devanagari


def rrf(rank_lists: list[list[int]], k: int = 60) -> list[tuple[int, float]]:
    scores: dict[int, float] = {}
    for lst in rank_lists:
        for r, idx in enumerate(lst, start=1):
            scores[idx] = scores.get(idx, 0.0) + 1.0 / (k + r)
    return sorted(scores.items(), key=lambda x: (-x[1], x[0]))


class Reranker:  # pragma: no cover - needs a downloaded model
    """Cross-encoder reranker, e.g. BAAI/bge-reranker-v2-m3 (568M, multilingual, XLM-RoBERTa-large base)."""

    def __init__(self, model_name: str):
        try:
            from sentence_transformers import CrossEncoder
        except ImportError as e:
            raise ImportError("pip install sentence-transformers  (needed for the reranker)") from e
        self.model = CrossEncoder(model_name, max_length=512)

    def rerank(self, query: str, chunks: list[Chunk]) -> list[float]:
        return [float(s) for s in self.model.predict([(query, c.text) for c in chunks])]


@dataclass
class RetrievalConfig:
    dense_k: int = 20
    sparse_k: int = 20
    rrf_k: int = 60
    final_k: int = 6


class HybridRetriever:
    def __init__(self, kb: KnowledgeBase, cfg: RetrievalConfig | None = None, reranker: Reranker | None = None):
        self.kb = kb
        self.cfg = cfg or RetrievalConfig()
        self.reranker = reranker

    def search(self, query: str, k: int | None = None, source_types=None, exclude_ids=None,
               exclude_shlokas=None, mode: str = "hybrid") -> list[Hit]:
        """mode: 'hybrid' | 'dense' | 'sparse' (the last two exist for the ablation experiment)."""
        k = k or self.cfg.final_k
        q = to_devanagari(query)
        allowed = self.kb.mask(source_types, exclude_ids, exclude_shlokas)
        lists: list[list[int]] = []
        if mode in ("hybrid", "dense"):
            qv = self.kb.embedder.embed_query(q)
            lists.append([i for i, _ in self.kb.dense.search(qv, self.cfg.dense_k, allowed)])
        if mode in ("hybrid", "sparse"):
            lists.append([i for i, _ in self.kb.bm25.search(bm25_tokens(q), self.cfg.sparse_k, allowed)])
        fused = rrf(lists, self.cfg.rrf_k) if len(lists) > 1 else [(i, 1.0 / (self.cfg.rrf_k + r))
                                                                   for r, i in enumerate(lists[0], 1)]
        cand = fused[: max(k * 3, k)] if self.reranker else fused[:k]
        if self.reranker and cand:
            chunks = [self.kb.chunks[i] for i, _ in cand]
            scores = self.reranker.rerank(q, chunks)
            cand = sorted(zip([i for i, _ in cand], scores), key=lambda x: -x[1])[:k]
        return [Hit(self.kb.chunks[i], s, r) for r, (i, s) in enumerate(cand, 1)]

    def context_for_step(self, shloka_id: str, query: str, source_types, k: int, step: int | None = None,
                         n_examples: int = 2, pinned_types=("mula", "commentary"),
                         exclude_shlokas_for_gold: bool = True) -> list[Hit]:
        """Context for one step of one shloka: structured lookup FIRST, semantic search SECOND.

        1. Pinned: every chunk explicitly linked to this shloka whose type the step uses (its own mula
           text, Dalhana's comment on it). These are always relevant, so we fetch them by id, not by luck.
        2. Searched: the remaining slots are filled by hybrid search (kosha, dhatu, cross-texts, examples).
        3. Leakage guard: 'gold' examples of THIS shloka are excluded, so the system never copies the answer
           it will later be evaluated against."""
        pinned = [c for c in self.kb.chunks_for_shloka(shloka_id)
                  if c.source_type in pinned_types and c.source_type in source_types]
        hits = [Hit(c, 1.0, r) for r, c in enumerate(pinned, 1)]
        seen = {c.id for c in pinned}
        remaining = max(k - len(hits), 0)
        if remaining:
            excl = [shloka_id] if exclude_shlokas_for_gold else []
            gold_free = [t for t in source_types if t != "gold"]
            searched: list[Hit] = []
            if gold_free:
                searched += self.search(query, remaining, source_types=gold_free, exclude_ids=seen)
            if "gold" in source_types and n_examples:   # few-shot examples of the SAME step, OTHER verses
                ex = self.search(query, 30, source_types=["gold"], exclude_shlokas=excl)
                searched += [h for h in ex if step is None or h.chunk.meta.get("step") == step][:n_examples]
            for h in searched:
                if h.chunk.id not in seen:
                    seen.add(h.chunk.id)
                    hits.append(Hit(h.chunk, h.score, len(hits) + 1))
        return hits
