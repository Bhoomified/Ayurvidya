"""Retrieval ablation: sparse vs dense vs hybrid on the labelled query set.

    python scripts/eval_retrieval.py --qrels data/eval/retrieval_qrels.jsonl
Run once per embedder (tfidf, bge-m3, qwen3-0.6B ...) and paste the tables into the paper.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")   # Devanagari on Windows consoles

from ayurvidya.config import load_settings  # noqa: E402
from ayurvidya.evaluation.retrieval_metrics import evaluate, load_qrels  # noqa: E402
from ayurvidya.index import KnowledgeBase  # noqa: E402
from ayurvidya.retrieve import HybridRetriever, RetrievalConfig  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--qrels", default="data/eval/retrieval_qrels.jsonl")
    args = ap.parse_args()
    s = load_settings()
    kb = KnowledgeBase.load(s.kb_dir)
    r = HybridRetriever(kb, RetrievalConfig(s.dense_k, s.sparse_k, s.rrf_k, s.final_k))
    report = evaluate(r, load_qrels(args.qrels))
    print(f"embedder = {s.embedder}")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
