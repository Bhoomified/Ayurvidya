"""Live walk-through of the RAG pipeline in the terminal, for presentations and viva.

    python scripts/demo.py                         # verse 13, step 4, all stages, pauses between them
    python scripts/demo.py --verse 22 --step 6     # another verse / step
    python scripts/demo.py --no-pause              # run straight through
    python scripts/demo.py --live                  # also re-generate this step NOW with the real AI (1-3 AI calls)
    python scripts/demo.py --ask "Which Vayu moves in the mouth?"   # also ask the chatbot (1 AI call)

Stages shown: 1 knowledge base -> 2 retrieval (BM25, dense, RRF fusion) -> 3 context the AI receives
-> 4 the saved answer -> 5 (optional) live generation with validation -> 6 (optional) chatbot.
Stages 1-4 need NO API key.
"""
from __future__ import annotations

import argparse
import sys
import textwrap
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from ayurvidya.index import bm25_tokens  # noqa: E402
from ayurvidya.ingest import load_mula  # noqa: E402
from ayurvidya.pipeline import format_context, neighbour_texts  # noqa: E402
from ayurvidya.retrieve import rrf  # noqa: E402
from ayurvidya.service import build_app  # noqa: E402
from ayurvidya.steps import STEP_SPECS, sampradanam  # noqa: E402
from ayurvidya.text import to_devanagari  # noqa: E402

BOLD, DIM, GOLD, GREEN, RED, END = "\033[1m", "\033[2m", "\033[33m", "\033[32m", "\033[31m", "\033[0m"
PAUSE = True


def stage(n: int, title: str, what: str) -> None:
    if PAUSE and n > 1:
        input(f"\n{DIM}Press Enter for stage {n}...{END}")
    print(f"\n{GOLD}{BOLD}{'=' * 78}\n STAGE {n}  {title}\n{'=' * 78}{END}")
    print(textwrap.fill(what, 78) + "\n")


def short(text: str, n: int = 90) -> str:
    t = " ".join(text.split())
    return t if len(t) <= n else t[: n - 1] + "…"


def show(hits_idx, kb, label: str) -> None:
    print(f"{BOLD}{label}{END}")
    for r, (i, score) in enumerate(hits_idx[:5], 1):
        c = kb.chunks[i]
        print(f"  {r}. {c.id:28s} {DIM}{c.source_type:10s} {score:.4f}{END}  {short(c.text, 60)}")


def main() -> None:
    global PAUSE
    ap = argparse.ArgumentParser()
    ap.add_argument("--verse", default="13")
    ap.add_argument("--step", type=int, default=4, choices=range(1, 8))
    ap.add_argument("--query", default=None, help="retrieval query for stage 2 (default: the verse's own words)")
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--ask", default=None)
    ap.add_argument("--no-pause", action="store_true")
    args = ap.parse_args()
    PAUSE = not args.no_pause and sys.stdin.isatty()

    app = build_app()
    kb, s = app.kb, app.settings
    shlokas, _ = load_mula(s.data_dir / "raw" / "niimh_su_ni_1_mula.json")
    idx = next((i for i, sh in enumerate(shlokas) if args.verse in sh.number.split("-")), None)
    if idx is None:
        sys.exit(f"verse {args.verse} not found")
    sh, spec = shlokas[idx], STEP_SPECS[args.step]

    # ------------------------------------------------------------------ 1
    stage(1, "KNOWLEDGE BASE  (what the system can look things up in)",
          "Every source text is cut into chunks (one verse, one commentary passage, one dictionary entry) and "
          "indexed twice: a keyword index (BM25) and a vector index (embeddings).")
    types = Counter(c.source_type for c in kb.chunks)
    print(f"  chunks: {BOLD}{len(kb.chunks)}{END}   " + "   ".join(f"{t}: {n}" for t, n in sorted(types.items())))
    print(f"  embedder: {s.embedder}   vector dimensions: {getattr(kb.dense, 'dim', '?')}   store: {s.db_path.name}")
    print(f"\n  Verse under study: {BOLD}{sh.id}{END}\n" + textwrap.indent(sh.text, "    "))

    # ------------------------------------------------------------------ 2
    query = args.query or spec.query(sh, {2: (app.store.steps(sh.id).get(2) or {}).get("output", "")})
    q = to_devanagari(query)
    stage(2, "RETRIEVAL  (find the most relevant chunks)",
          "The same query goes to two retrievers. BM25 matches exact Sanskrit word pieces (good for sandhi); "
          "the dense retriever matches meaning. Reciprocal Rank Fusion merges the two ranked lists: "
          f"score = sum of 1/(60 + rank).")
    print(f"  query: {short(q, 70)}\n")
    t0 = time.time()
    sparse = kb.bm25.search(bm25_tokens(q), s.sparse_k, None)
    dense = kb.dense.search(kb.embedder.embed_query(q), s.dense_k, None)
    fused = rrf([[i for i, _ in dense], [i for i, _ in sparse]], s.rrf_k)
    ms = (time.time() - t0) * 1000
    show(sparse, kb, "BM25 (keywords)")
    show(dense, kb, "\nDense (meaning)")
    show(fused, kb, "\nRRF fusion (final ranking)")
    print(f"\n  {DIM}retrieval took {ms:.0f} ms over {len(kb.chunks)} chunks{END}")

    # ------------------------------------------------------------------ 3
    prev = {n: d["output"] for n, d in app.store.steps(sh.id).items()}
    prev.setdefault(1, sampradanam(sh))
    stage(3, f"AUGMENTATION  (build the prompt for step {spec.number}: {spec.name})",
          "For one step of one verse the context is: the verse itself (pinned), its commentary (pinned), "
          "searched references of the kinds this step needs, two worked examples of the SAME step on OTHER "
          "verses (never this verse's own answer: leakage guard), and the outputs of earlier steps.")
    if not spec.uses_llm:
        print(f"  Step 1 needs no AI: it is computed by rules (danda positions, syllable count).\n\n{sampradanam(sh)}")
    else:
        hits = app.retriever.context_for_step(sh.id, spec.query(sh, prev), spec.source_types, spec.k, step=spec.number)
        system, version = spec.prompt(s.prompts_dir)
        user = format_context(spec, sh, prev, hits, neighbour_texts(shlokas, idx))
        print(f"  step uses source types: {', '.join(spec.source_types)}")
        for h in hits:
            kind = "pinned " if h.score == 1.0 and h.chunk.shloka_ids == [sh.id] else ("example" if h.chunk.source_type == "gold" else "search ")
            print(f"  {kind}  {h.chunk.id:28s} {DIM}{h.chunk.source_type}{END}")
        print(f"\n  system prompt: {len(system)} characters (step rules + grounding rules, version {version})")
        print(f"  user message:  {len(user)} characters. First lines:\n")
        print(textwrap.indent("\n".join(user.splitlines()[:14]), "    " + DIM) + END)

    # ------------------------------------------------------------------ 4
    stage(4, "GENERATION  (the saved answer)",
          "All 90 verses x 7 steps were generated once and saved in the database, so students get answers "
          "instantly and no API key is needed to view them.")
    saved = app.store.steps(sh.id).get(spec.number)
    if saved:
        print(f"  model: {saved['model']}   format check: {GREEN + 'passed' + END if saved['valid'] else RED + 'failed' + END}"
              f"   cites: {', '.join(saved['retrieved_ids'][:4]) or '-'}\n")
        print(textwrap.indent(saved["output"][:1500], "    "))
    else:
        print(f"  {RED}Not in this database yet.{END} Run: python scripts/share_answers.py import  (or generate it)")

    # ------------------------------------------------------------------ 5
    if args.live and spec.uses_llm:
        stage(5, "LIVE GENERATION  (call the AI now and validate)",
              "The AI writes the step; a validator checks the format (word count, '=' pairs, English, ...). "
              "If it fails, the AI is asked again with the list of problems.")
        if app.orchestrator.llm.name == "mock":
            print(f"  {RED}AYV_LLM is 'mock' - put the real model and key in .env to run this stage.{END}")
        else:
            t0 = time.time()
            r = app.orchestrator.run_step(spec, sh, prev, force=True, neighbours=neighbour_texts(shlokas, idx))
            print(f"  {r.attempts} attempt(s), {time.time() - t0:.1f} s, valid: {r.valid} {r.issues or ''}\n")
            print(textwrap.indent(r.output[:1500], "    "))

    # ------------------------------------------------------------------ 6
    if args.ask:
        stage(6, "CHATBOT  (grounded doubt-clearing)",
              "The question is answered from this verse, its 7 saved steps and a fresh hybrid search. The answer "
              "must cite its sources; if nothing relevant is found it says so instead of guessing.")
        try:
            a = app.chatbot.ask(args.ask, sh.id)
            print(f"  {BOLD}Q:{END} {args.ask}\n  {BOLD}A:{END} {a.answer}\n  {DIM}sources: {', '.join(a.citations) or '-'}   grounded: {a.grounded}{END}")
        except Exception as e:  # no key / quota
            print(f"  {RED}{e}{END}")
    print(f"\n{GOLD}Done.{END}")


if __name__ == "__main__":
    main()