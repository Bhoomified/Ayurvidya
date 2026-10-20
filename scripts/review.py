"""Scholar review of the AI outputs, through Excel.

    python scripts/review.py export                         # all outputs -> outputs/review/review_<date>.xlsx
    python scripts/review.py export --status generated      # only the ones not reviewed yet
    python scripts/review.py export --verses 3 4 5          # only these verses
    python scripts/review.py import outputs/review/review_2026-10-20.xlsx --dry-run   # check first
    python scripts/review.py import outputs/review/review_2026-10-20.xlsx             # save to database
    python scripts/review.py summary                        # how much is reviewed / approved

The scholar fills the yellow columns: status (generated / reviewed / approved), corrected_output, reviewer_note.
A backup of the database is made automatically before every import.
"""
from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from backup_db import backup  # noqa: E402  (scripts/backup_db.py)

from ayurvidya.config import load_settings  # noqa: E402
from ayurvidya.review import export_review, import_review, review_summary  # noqa: E402
from ayurvidya.store import Store  # noqa: E402

CHAPTER = "su.ni.1"


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("export")
    e.add_argument("--status", choices=("generated", "reviewed", "approved"))
    e.add_argument("--verses", nargs="+")
    e.add_argument("--out", default=None)
    i = sub.add_parser("import")
    i.add_argument("file")
    i.add_argument("--dry-run", action="store_true", help="only check, do not save")
    sub.add_parser("summary")
    args = ap.parse_args()

    s = load_settings()
    if not s.db_path.exists():
        sys.exit("No database yet. Run: python scripts/build_kb.py")
    if args.cmd == "import" and not args.dry_run:
        print("backup:", backup(s.db_path).relative_to(ROOT))
    store = Store(s.db_path)

    if args.cmd == "export":
        out = Path(args.out or ROOT / "outputs" / "review" / f"review_{date.today()}.xlsx")
        n = export_review(store, CHAPTER, out, args.status, set(args.verses) if args.verses else None)
        print(f"{n} rows -> {out}")
        print("Give this file to the scholar. They fill the yellow columns, then: python scripts/review.py import <file>")
    elif args.cmd == "import":
        r = import_review(store, args.file, dry_run=args.dry_run)
        print(f"{'WOULD UPDATE' if args.dry_run else 'updated'}: {r['updated']} "
              f"(with corrected text: {r['corrected']}), unchanged: {r['unchanged']}")
        for p in r["problems"]:
            print("  problem:", p)
    print("summary:", review_summary(store, CHAPTER))
    store.close()


if __name__ == "__main__":
    main()