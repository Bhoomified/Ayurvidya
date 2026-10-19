"""Knowledge-base health check (task B6). Run after every build_kb.py.

    python scripts/kb_report.py                     # prints the report
    python scripts/kb_report.py --save outputs/kb_report.md

Checks: chunk counts per type, which verses have commentary / parallels, empty or duplicate texts,
text that is not in normalised form, leftover '|' dandas, and shows sample chunks to read by eye.
"""
from __future__ import annotations

import argparse
import json
import random
import sys
import unicodedata
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from ayurvidya.config import load_settings  # noqa: E402
from ayurvidya.ingest import load_chunks  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--save", default=None)
    ap.add_argument("--samples", type=int, default=3, help="sample chunks shown per type")
    args = ap.parse_args()
    s = load_settings()
    kb = s.kb_dir
    if not (kb / "chunks.jsonl").exists():
        sys.exit("No knowledge base yet. Run: python scripts/build_kb.py")
    manifest = json.loads((kb / "manifest.json").read_text(encoding="utf-8"))
    chunks = load_chunks(kb / "chunks.jsonl")

    lines = ["# Knowledge-base report", "",
             f"- embedder: `{manifest['embedder']}` - dimensions: {manifest['dim']} - store: {manifest['vector_store']}",
             f"- total chunks: **{len(chunks)}**", "", "## Chunks per type", "", "| type | chunks |", "| --- | --- |"]
    for t, n in sorted(Counter(c.source_type for c in chunks).items()):
        lines.append(f"| {t} | {n} |")

    verses = sorted({sid for c in chunks if c.source_type == "mula" for sid in c.shloka_ids},
                    key=lambda x: int(x.rsplit(".", 1)[1].split("-")[0]))
    lines += ["", "## Coverage per verse", ""]
    for t in ("commentary", "kosha", "dhatu", "crosstext", "gold"):
        have = {sid for c in chunks if c.source_type == t for sid in c.shloka_ids}
        miss = [v.rsplit(".", 1)[1] for v in verses if v not in have]
        lines.append(f"- **{t}**: {len(verses) - len(miss)}/{len(verses)} verses"
                     + (f" - missing: {', '.join(miss[:40])}{' ...' if len(miss) > 40 else ''}" if miss else ""))

    problems = []
    texts = Counter(c.text for c in chunks)
    for c in chunks:
        if not c.text.strip():
            problems.append(f"{c.id}: empty text")
        if unicodedata.normalize("NFC", c.text) != c.text:
            problems.append(f"{c.id}: not NFC-normalised")
        if "|" in c.text and c.source_type != "gold":
            problems.append(f"{c.id}: contains '|' (should be । or ॥)")
        if texts[c.text] > 1 and c.source_type != "gold":
            problems.append(f"{c.id}: duplicate text")
    lines += ["", f"## Problems found: {len(problems)}", ""] + [f"- {p}" for p in problems[:100]]

    lines += ["", "## Samples to read by eye", ""]
    rng = random.Random(7)
    by_type: dict[str, list] = {}
    for c in chunks:
        by_type.setdefault(c.source_type, []).append(c)
    for t, cs in sorted(by_type.items()):
        for c in rng.sample(cs, min(args.samples, len(cs))):
            lines += [f"**{c.id}** ({t}, {c.work})", "", "```", c.text[:400], "```", ""]

    report = "\n".join(lines)
    print(report)
    if args.save:
        Path(args.save).parent.mkdir(parents=True, exist_ok=True)
        Path(args.save).write_text(report, encoding="utf-8")
        print(f"\nsaved to {args.save}")


if __name__ == "__main__":
    main()