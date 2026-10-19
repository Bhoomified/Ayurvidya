"""Retrieval quality on a labelled query set (qrels).

data/eval/retrieval_qrels.jsonl — one line per query, written by the team with a scholar:
  {"qid": "q01", "query": "Which Vayu moves in the mouth?", "relevant": ["mula.su.ni.1.13"], "step": null}

Metrics (all in [0, 1], higher is better):
  Recall@k   share of the relevant chunks found in the top k
  MRR        1 / rank of the first relevant chunk (0 if none in the list)
  nDCG@k     rank-aware gain with binary relevance
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from statistics import mean


def recall_at_k(ranked: list[str], relevant: set[str], k: int) -> float:
    return len(set(ranked[:k]) & relevant) / len(relevant) if relevant else 0.0


def mrr(ranked: list[str], relevant: set[str]) -> float:
    for r, cid in enumerate(ranked, 1):
        if cid in relevant:
            return 1.0 / r
    return 0.0


def ndcg_at_k(ranked: list[str], relevant: set[str], k: int) -> float:
    dcg = sum(1.0 / math.log2(r + 1) for r, cid in enumerate(ranked[:k], 1) if cid in relevant)
    ideal = sum(1.0 / math.log2(r + 1) for r in range(1, min(len(relevant), k) + 1))
    return dcg / ideal if ideal else 0.0


def load_qrels(path: str | Path) -> list[dict]:
    return [json.loads(l) for l in Path(path).read_text(encoding="utf-8").splitlines() if l.strip()]


def evaluate(retriever, qrels: list[dict], ks=(1, 3, 5, 10), modes=("sparse", "dense", "hybrid")) -> dict:
    """Runs every query in every retrieval mode -> the ablation table for the paper."""
    report = {}
    for mode in modes:
        rows = []
        for q in qrels:
            ranked = [h.chunk.id for h in retriever.search(q["query"], k=max(ks), mode=mode,
                                                           source_types=[t for t in q.get("types", []) or []] or None)]
            rel = set(q["relevant"])
            row = {f"recall@{k}": recall_at_k(ranked, rel, k) for k in ks}
            row["mrr"] = mrr(ranked, rel)
            row[f"ndcg@{max(ks)}"] = ndcg_at_k(ranked, rel, max(ks))
            rows.append(row)
        report[mode] = {m: round(mean(r[m] for r in rows), 4) for m in rows[0]} if rows else {}
    return report
