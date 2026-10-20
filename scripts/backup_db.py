"""Safe copy of the database (all generated + reviewed outputs). Run before every big AI run or import.

    python scripts/backup_db.py              # -> data/backups/ayurvidya_<date>_<time>.sqlite3 (keeps last 10)
    python scripts/backup_db.py --list
    python scripts/backup_db.py --restore data/backups/ayurvidya_20261020_1530.sqlite3

data/backups/ is not in Git (too big, changes often). Copy the newest backup to the shared Google Drive
folder once a week so it is not only on one laptop.
"""
from __future__ import annotations

import argparse
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from ayurvidya.config import load_settings  # noqa: E402

KEEP = 10


def backup_dir() -> Path:
    return load_settings().data_dir / "backups"


def backup(db_path: Path, keep: int = KEEP) -> Path:
    """Consistent copy using SQLite's own backup (safe even while the app has the file open)."""
    d = backup_dir()
    d.mkdir(parents=True, exist_ok=True)
    dest = d / f"ayurvidya_{datetime.now():%Y%m%d_%H%M%S}.sqlite3"
    src, dst = sqlite3.connect(str(db_path)), sqlite3.connect(str(dest))
    with dst:
        src.backup(dst)
    src.close()
    dst.close()
    for old in sorted(d.glob("ayurvidya_*.sqlite3"))[:-keep]:
        old.unlink()
    return dest


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--restore", default=None)
    args = ap.parse_args()
    s = load_settings()
    if args.list:
        for p in sorted(backup_dir().glob("ayurvidya_*.sqlite3")):
            print(f"{p.name}  {p.stat().st_size / 1024:.0f} KB")
        return
    if args.restore:
        src = Path(args.restore)
        if not src.exists():
            sys.exit(f"not found: {src}")
        if s.db_path.exists():
            print("current database saved first as", backup(s.db_path).name)
        shutil.copyfile(src, s.db_path)
        print(f"restored {src.name} -> {s.db_path.name}")
        return
    if not s.db_path.exists():
        sys.exit("No database yet. Run: python scripts/build_kb.py")
    print("backup:", backup(s.db_path))


if __name__ == "__main__":
    main()