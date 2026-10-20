"""Turn the filled-in word_list.csv into knowledge-base files.

    python scripts/words_to_jsonl.py

Reads  data/sources/word_list.csv
Writes data/sources/amarakosha_su_ni_1.jsonl   (one entry per word with a 'kosha' value)
       data/sources/dhatupatha_su_ni_1.jsonl   (one entry per word with a 'dhatu' value)
Each entry is linked to the verses the word occurs in, so retrieval can find it for that verse.
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

from ayurvidya.text import normalize  # noqa: E402

SRC = ROOT / "data" / "sources"
JOINED = {"1": "1-2", "2": "1-2"}          # verses 1 and 2 are one unit in the app


def sid(n: str) -> str:
    return f"su.ni.1.{JOINED.get(n, n)}"


def main() -> None:
    path = SRC / "word_list.csv"
    if not path.exists():
        sys.exit("No word_list.csv yet. Run: python scripts/make_word_list.py")
    with open(path, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))

    out = {"kosha": [], "dhatu": []}
    for r in rows:
        word = normalize(r.get("word", "")).strip()
        verses = [v.strip() for v in (r.get("verses") or "").split(",") if v.strip()]
        ids = sorted({sid(v) for v in verses})
        for col, work, prefix in (("kosha", "Amarakosha", "amara"), ("dhatu", "Dhatupatha", "dhatu")):
            val = normalize(r.get(col) or "").strip()
            if word and val:
                out[col].append({"id": f"{prefix}.{word}", "source_type": col, "work": work,
                                 "text": f"{word} — {val}", "shloka_ids": ids, "headword": word})

    for col, fname in (("kosha", "amarakosha_su_ni_1.jsonl"), ("dhatu", "dhatupatha_su_ni_1.jsonl")):
        p = SRC / fname
        if not out[col]:
            p.unlink(missing_ok=True)
            print(f"{fname}: no '{col}' values filled in yet")
            continue
        p.write_text("".join(json.dumps(d, ensure_ascii=False) + "\n" for d in out[col]), encoding="utf-8")
        print(f"{fname}: {len(out[col])} entries")
    print("Next: python scripts/build_kb.py   then   python scripts/kb_report.py")


if __name__ == "__main__":
    main()