"""Write the test questions for retrieval in Excel instead of JSON.

    python scripts/queries_csv.py export     # data/eval/retrieval_qrels.jsonl -> data/eval/queries.csv
    python scripts/queries_csv.py import     # data/eval/queries.csv -> data/eval/retrieval_qrels.jsonl

queries.csv columns:
    qid      q01, q02, ...
    query    the question, in English, Devanagari or IAST
    verses   the verse number(s) that answer it, e.g. 13  or  12,13
    types    where the answer should come from: mula (default), commentary, kosha, dhatu, crosstext
             several allowed, e.g. mula,commentary
    note     anything (who wrote it, why)

On import the verse numbers are turned into the matching chunk ids of the current knowledge base,
so build the KB first (python scripts/build_kb.py). Aim for 100+ questions, checked by a scholar.
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from ayurvidya.config import load_settings  # noqa: E402
from ayurvidya.ingest import load_chunks  # noqa: E402

EVAL = ROOT / "data" / "eval"
JSONL, CSV = EVAL / "retrieval_qrels.jsonl", EVAL / "queries.csv"
FIELDS = ["qid", "query", "verses", "types", "note"]


def verse_of(sid: str) -> str:
    return sid.rsplit(".", 1)[1]


def export() -> None:
    chunks = {c.id: c for c in load_chunks(load_settings().kb_dir / "chunks.jsonl")}
    rows = []
    for line in JSONL.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        q = json.loads(line)
        verses = sorted({verse_of(s) for cid in q["relevant"] if cid in chunks for s in chunks[cid].shloka_ids},
                        key=lambda v: int(v.split("-")[0]))
        rows.append({"qid": q["qid"], "query": q["query"], "verses": ",".join(verses),
                     "types": ",".join(q.get("types") or ["mula"]), "note": q.get("note", "")})
    with open(CSV, "w", encoding="utf-8-sig", newline="") as f:
        wr = csv.DictWriter(f, FIELDS)
        wr.writeheader()
        wr.writerows(rows)
    print(f"{len(rows)} questions -> {CSV.relative_to(ROOT)}  (open in Excel, add rows, save as CSV UTF-8)")


def import_() -> None:
    chunks = load_chunks(load_settings().kb_dir / "chunks.jsonl")
    with open(CSV, encoding="utf-8-sig", newline="") as f:
        rows = [r for r in csv.DictReader(f) if (r.get("query") or "").strip()]
    out, problems = [], []
    for n, r in enumerate(rows, 1):
        qid = (r.get("qid") or "").strip() or f"q{n:03d}"
        verses = {v.strip() for v in (r.get("verses") or "").split(",") if v.strip()}
        types = [t.strip() for t in (r.get("types") or "mula").split(",") if t.strip()]
        rel = [c.id for c in chunks if c.source_type in types
               and any(v in verse_of(s).split("-") for s in c.shloka_ids for v in verses)]
        if not rel:
            problems.append(f"{qid}: no {'/'.join(types)} chunk for verse(s) {sorted(verses)}")
            continue
        out.append({"qid": qid, "query": r["query"].strip(), "relevant": rel, "types": types,
                    "note": (r.get("note") or "").strip()})
    JSONL.write_text("".join(json.dumps(q, ensure_ascii=False) + "\n" for q in out), encoding="utf-8")
    print(f"{len(out)} questions -> {JSONL.relative_to(ROOT)}")
    for p in problems:
        print("  skipped", p)


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in ("export", "import"):
        sys.exit(__doc__)
    export() if sys.argv[1] == "export" else import_()