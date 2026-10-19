"""Show EXACTLY what the AI model receives for one step of one verse (no AI call, free).
Use it to understand the pipeline (task V2) and to debug a bad answer.

    python scripts/show_context.py --verse 3 --step 4
    python scripts/show_context.py --verse 13 --step 2 --save outputs/context_13_2.txt
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from ayurvidya.config import load_settings  # noqa: E402
from ayurvidya.index import KnowledgeBase  # noqa: E402
from ayurvidya.ingest import load_mula  # noqa: E402
from ayurvidya.pipeline import format_context, neighbour_texts  # noqa: E402
from ayurvidya.retrieve import HybridRetriever, RetrievalConfig  # noqa: E402
from ayurvidya.steps import STEP_SPECS, sampradanam  # noqa: E402
from ayurvidya.store import Store  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--verse", required=True, help="verse number, e.g. 3 (use 1 for the joined 1-2)")
    ap.add_argument("--step", type=int, required=True, choices=range(1, 8))
    ap.add_argument("--save", default=None, help="also write the context to this file")
    args = ap.parse_args()

    s = load_settings()
    shlokas, _ = load_mula(s.data_dir / "raw" / "niimh_su_ni_1_mula.json")
    idx = next((i for i, sh in enumerate(shlokas) if args.verse in sh.number.split("-")), None)
    if idx is None:
        sys.exit(f"verse {args.verse} not found")
    sh, spec = shlokas[idx], STEP_SPECS[args.step]

    if not spec.uses_llm:
        print(f"Step 1 is rule-based (no AI). Output for {sh.id}:\n\n{sampradanam(sh)}")
        return

    kb = KnowledgeBase.load(s.kb_dir)
    retriever = HybridRetriever(kb, RetrievalConfig(s.dense_k, s.sparse_k, s.rrf_k, s.final_k))
    store = Store(s.db_path)
    prev = {n: d["output"] for n, d in store.steps(sh.id).items()}
    prev.setdefault(1, sampradanam(sh))
    missing = [k for k in spec.prev_steps if k not in prev]

    system, version = spec.prompt(s.prompts_dir)
    hits = retriever.context_for_step(sh.id, spec.query(sh, prev), spec.source_types, spec.k, step=spec.number)
    user = format_context(spec, sh, prev, hits, neighbour_texts(shlokas, idx))

    out = [f"=== SYSTEM PROMPT (step {spec.number}, version {version}) ===", system,
           "", "=== USER MESSAGE (the context) ===", user, "",
           "=== RETRIEVED CHUNKS ===",
           *[f"{h.rank:>2}. {h.chunk.id:32s} type={h.chunk.source_type:10s} score={h.score:.4f}" for h in hits]]
    if missing:
        out += ["", f"NOTE: earlier step(s) {missing} not generated yet for this verse, so they are missing above. "
                    "Run the pipeline for this verse first to see the full context."]
    text = "\n".join(out)
    print(text)
    if args.save:
        Path(args.save).parent.mkdir(parents=True, exist_ok=True)
        Path(args.save).write_text(text, encoding="utf-8")
        print(f"\nsaved to {args.save}")
    store.close()


if __name__ == "__main__":
    main()