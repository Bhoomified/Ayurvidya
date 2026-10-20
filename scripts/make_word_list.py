"""Make the list of every word in the chapter, to fill in Amarakosha meanings and Dhatupatha roots.

    python scripts/make_word_list.py

Writes data/sources/word_list.csv (opens in Excel) with columns:
    word | verses | kosha | dhatu
Fill in 'kosha' (the Amarakosha line / synonyms) and 'dhatu' (root + meaning, e.g. "भू सत्तायाम् (भ्वादिः)")
for the words you can; leave the rest empty. In Excel save as "CSV UTF-8". Then run words_to_jsonl.py.
Running this again keeps everything you already filled in and only adds new words.

Words come from the Padavibhaga of the gold table (verses 1-30, already split), and for the other verses
from the mula text split at spaces (those may still be joined by sandhi - split them by hand if needed).
"""
from __future__ import annotations

import csv
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from ayurvidya.ingest import load_gold_xlsx, load_mula  # noqa: E402
from ayurvidya.text import strip_verse_markers  # noqa: E402

OUT = ROOT / "data" / "sources" / "word_list.csv"
FIELDS = ["word", "verses", "kosha", "dhatu"]


def clean(w: str) -> str:
    return re.sub(r"[^\u0900-\u097F]", "", w).strip("।॥ऽ")


def words_by_verse() -> dict[str, list[str]]:
    shlokas, _ = load_mula(ROOT / "data" / "raw" / "niimh_su_ni_1_mula.json")
    gold: dict[str, dict[int, str]] = {}
    for g in sorted((ROOT / "data" / "gold").glob("*.xlsx")):
        gold.update(load_gold_xlsx(g))
    out = {}
    for sh in shlokas:
        pada = gold.get(sh.id, {}).get(2, "")
        if pada:
            first = pada.splitlines()[0]                 # "w1 | w2 | w3"
            words = [clean(w) for w in first.split("|")]
        else:
            words = [clean(w) for w in strip_verse_markers(sh.text).split()]
        out[sh.number] = [w for w in words if len(w) > 1]
    return out


def main() -> None:
    old: dict[str, dict] = {}
    if OUT.exists():
        with open(OUT, encoding="utf-8-sig", newline="") as f:
            old = {r["word"]: r for r in csv.DictReader(f)}

    rows: dict[str, dict] = {}
    for num, words in words_by_verse().items():
        for w in words:
            r = rows.setdefault(w, {"word": w, "verses": [], "kosha": "", "dhatu": ""})
            if num not in r["verses"]:
                r["verses"].append(num)
    for w, r in rows.items():
        r["verses"] = ",".join(r["verses"])
        if w in old:
            r["kosha"], r["dhatu"] = old[w].get("kosha", ""), old[w].get("dhatu", "")
    for w, r in old.items():          # keep words you added by hand
        rows.setdefault(w, r)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", encoding="utf-8-sig", newline="") as f:   # utf-8-sig: Excel shows Devanagari
        wr = csv.DictWriter(f, FIELDS, extrasaction="ignore")
        wr.writeheader()
        wr.writerows(rows.values())
    filled = sum(1 for r in rows.values() if r.get("kosha") or r.get("dhatu"))
    print(f"{len(rows)} words -> {OUT.relative_to(ROOT)}  ({filled} already filled in)")


if __name__ == "__main__":
    main()