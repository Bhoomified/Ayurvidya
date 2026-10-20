"""Type or paste commentary / parallel-text passages into the knowledge base, one verse at a time.

    python scripts/add_source.py dalhana            # Dalhana's commentary
    python scripts/add_source.py gayadasa           # Gayadasa's commentary
    python scripts/add_source.py charaka            # Charaka Ci. 28 parallels
    python scripts/add_source.py ahr                # Ashtanga Hridaya Ni. 16 parallels
    python scripts/add_source.py dalhana --status   # which verses are done / still missing

For each passage: give the Sushruta verse number it belongs to, paste the text, then type END on its
own line. Type Q as the verse number to stop. '|' and '||' are turned into । and ॥ automatically.
Everything is saved in data/sources/<file>.txt in the format build_kb.py reads.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stdin, "reconfigure"):
    sys.stdin.reconfigure(encoding="utf-8")

from ayurvidya.ingest import load_mula  # noqa: E402
from ayurvidya.text import normalize  # noqa: E402

PRESETS = {  # name -> (file name, source_type, work)
    "dalhana":  ("dalhana_su_ni_1.txt", "commentary", "Nibandhasangraha (Dalhana)"),
    "gayadasa": ("gayadasa_su_ni_1.txt", "commentary", "Nyayachandrika (Gayadasa)"),
    "charaka":  ("charaka_ci_28.txt", "crosstext", "Charaka Samhita Chikitsa 28"),
    "ahr":      ("ahr_ni_16.txt", "crosstext", "Ashtanga Hridaya Nidana 16"),
}


def verse_numbers() -> list[str]:
    """Verse units of the chapter as the app uses them: ['1-2', '3', '4', ...] (1 and 2 are one unit)."""
    shlokas, _ = load_mula(ROOT / "data" / "raw" / "niimh_su_ni_1_mula.json")
    return [sh.number for sh in shlokas]


def done_verses(path: Path) -> set[str]:
    if not path.exists():
        return set()
    out = set()
    for m in re.finditer(r"^#\s*shloka\s*:\s*(.+)$", path.read_text(encoding="utf-8"), re.M):
        out.update(n.strip() for n in m.group(1).split(",") if n.strip())
    return out


def block(verses: str, text: str) -> str:
    return f"# shloka: {verses}\n{normalize(text).strip()}\n"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("work", choices=sorted(PRESETS))
    ap.add_argument("--status", action="store_true", help="only show which verses are done")
    args = ap.parse_args()
    fname, st, work = PRESETS[args.work]
    path = ROOT / "data" / "sources" / fname
    allv = verse_numbers()

    done = done_verses(path)
    missing = [v for v in allv if v not in done]
    print(f"{work}  ->  data/sources/{fname}")
    print(f"done {len(done & set(allv))}/{len(allv)} verses. Missing: {', '.join(missing) or 'none'}")
    if args.status:
        return

    if not path.exists():
        path.write_text(f"# source_type: {st}\n# work: {work}\n# chapter: 1\n", encoding="utf-8")
    while True:
        v = input("\nVerse number (e.g. 3, or 21,22 for several; Q to quit): ").strip()
        if v.upper() == "Q":
            break
        nums = [("1-2" if n.strip() in ("1", "2") else n.strip()) for n in v.split(",") if n.strip()]
        bad = [n for n in nums if n not in allv]
        if not nums or bad:
            print(f"  not a verse of this chapter: {bad or v}")
            continue
        if set(nums) & done:
            if input(f"  verse {v} already has a passage; add another one? (y/n): ").strip().lower() != "y":
                continue
        print("  Paste the text, then type END on its own line:")
        lines = []
        while (line := input()).strip() != "END":
            lines.append(line)
        text = "\n".join(lines).strip()
        if not text:
            print("  nothing pasted, skipped")
            continue
        with open(path, "a", encoding="utf-8") as f:
            f.write(block(",".join(nums), text))
        done.update(nums)
        print(f"  saved verse {v} ({len(text)} characters)")
    print("\nNext: python scripts/build_kb.py   then   python scripts/kb_report.py")


if __name__ == "__main__":
    main()