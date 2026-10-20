"""Compare embedding models on the test questions (which one finds the right verse best?).

    python scripts/compare_embedders.py                              # tfidf, bge-m3, Qwen3-0.6B
    python scripts/compare_embedders.py tfidf st:BAAI/bge-m3         # only these

Needs: pip install -r requirements.txt  (first run downloads each model, ~1-2.5 GB, once).
Each model gets its own temporary KB in outputs/kb_compare/ - your real data/kb is not touched.
Result table: outputs/embedder_comparison.md. Put the winner in .env as AYV_EMBEDDER=... and rebuild.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from build_kb import topics_from_gold  # noqa: E402  (scripts/build_kb.py)

from ayurvidya.config import load_settings  # noqa: E402
from ayurvidya.evaluation.retrieval_metrics import evaluate, load_qrels  # noqa: E402
from ayurvidya.index import KnowledgeBase  # noqa: E402
from ayurvidya.ingest import build_chunks, load_gold_xlsx, load_mula  # noqa: E402
from ayurvidya.retrieve import HybridRetriever, RetrievalConfig  # noqa: E402

DEFAULT = ["tfidf", "st:BAAI/bge-m3", "st:Qwen/Qwen3-Embedding-0.6B"]


def main() -> None:
    specs = sys.argv[1:] or DEFAULT
    s = load_settings()
    gold_files = sorted((s.data_dir / "gold").glob("*.xlsx"))
    shlokas, _ = load_mula(s.data_dir / "raw" / "niimh_su_ni_1_mula.json", topics=topics_from_gold(gold_files))
    gold = {}
    for g in gold_files:
        gold.update(load_gold_xlsx(g))
    sources = sorted(p for p in (s.data_dir / "sources").glob("*") if p.suffix in (".txt", ".jsonl"))
    chunks = build_chunks(shlokas, gold, sources)
    qrels = load_qrels(s.data_dir / "eval" / "retrieval_qrels.jsonl")
    print(f"{len(chunks)} chunks, {len(qrels)} test questions\n")

    lines = ["# Embedder comparison", "", f"{len(chunks)} chunks, {len(qrels)} questions", "",
             "| embedder | mode | recall@1 | recall@5 | recall@10 | MRR | nDCG@10 | build s |",
             "| --- | --- | --- | --- | --- | --- | --- | --- |"]
    for spec in specs:
        print(f"== {spec}")
        kb_dir = ROOT / "outputs" / "kb_compare" / spec.replace(":", "_").replace("/", "_")
        t0 = time.time()
        try:
            KnowledgeBase.build(chunks, spec, kb_dir, s.vector_store)
        except Exception as e:   # model not installed / download failed
            print(f"   FAILED: {e}\n")
            lines.append(f"| {spec} | failed: {str(e)[:60]} | | | | | | |")
            continue
        secs = time.time() - t0
        r = HybridRetriever(KnowledgeBase.load(kb_dir), RetrievalConfig(s.dense_k, s.sparse_k, s.rrf_k, s.final_k))
        for mode, m in evaluate(r, qrels).items():
            lines.append(f"| {spec} | {mode} | {m['recall@1']} | {m['recall@5']} | {m['recall@10']} "
                         f"| {m['mrr']} | {m['ndcg@10']} | {secs:.0f} |")
            print(f"   {mode:6s}  recall@5={m['recall@5']}  MRR={m['mrr']}")
        print()

    out = ROOT / "outputs" / "embedder_comparison.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    print(f"\nsaved to {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()