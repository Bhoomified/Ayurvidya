"""Share the generated 7-step answers between computers through Git (no API key needed to view them).

The answers live in data/ayurvidya.sqlite3, which is NOT in Git. This script copies them to a small text
file that IS in Git, and back.

    python scripts/share_answers.py export     # database -> data/generated/su_ni_1_steps.jsonl  (then commit + push)
    python scripts/share_answers.py import     # after git pull: data/generated/... -> database

Import rule when both sides have the same verse + step: the more-checked one wins
(approved > reviewed > generated); if equal, the newer one wins. A backup is made first.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from ayurvidya.config import load_settings  # noqa: E402
from ayurvidya.store import Store  # noqa: E402

FILE = ROOT / "data" / "generated" / "su_ni_1_steps.jsonl"
COLS = ["shloka_id", "step_number", "output", "valid", "issues", "retrieved_ids", "model", "prompt_version",
        "status", "reviewer_note", "created_at"]
RANK = {"generated": 0, "reviewed": 1, "approved": 2}


def export(store: Store) -> None:
    rows = store.db.execute(f"SELECT {', '.join(COLS)} FROM shloka_steps ORDER BY shloka_id, step_number").fetchall()
    FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(FILE, "w", encoding="utf-8", newline="\n") as f:
        for r in rows:
            f.write(json.dumps(dict(r), ensure_ascii=False) + "\n")
    print(f"{len(rows)} answers -> {FILE.relative_to(ROOT)}")
    print("Now: git add data/generated && git commit -m \"Update generated answers\" && git push")


def import_(store: Store, db_path: Path) -> None:
    if not FILE.exists():
        sys.exit(f"{FILE.relative_to(ROOT)} not found. Run git pull first.")
    if not store.shlokas("su.ni.1"):
        sys.exit("The database has no verses yet. Run first:  python scripts/build_kb.py")
    sys.path.insert(0, str(ROOT / "scripts"))
    from backup_db import backup
    print("backup:", backup(db_path).name)
    added = replaced = kept = 0
    with store.db:
        for line in FILE.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            new = json.loads(line)
            old = store.db.execute("SELECT status, created_at FROM shloka_steps WHERE shloka_id=? AND step_number=?",
                                   (new["shloka_id"], new["step_number"])).fetchone()
            if old is not None:
                better = (RANK.get(new["status"], 0), new["created_at"]) > (RANK.get(old["status"], 0), old["created_at"])
                if not better:
                    kept += 1
                    continue
                replaced += 1
            else:
                added += 1
            store.db.execute(f"INSERT OR REPLACE INTO shloka_steps ({', '.join(COLS)}) VALUES ({', '.join('?' * len(COLS))})",
                             [new[c] for c in COLS])
    print(f"added {added}, updated {replaced}, kept local {kept}")


def main() -> None:
    if len(sys.argv) != 2 or sys.argv[1] not in ("export", "import"):
        sys.exit(__doc__)
    s = load_settings()
    store = Store(s.db_path)
    export(store) if sys.argv[1] == "export" else import_(store, s.db_path)
    store.close()


if __name__ == "__main__":
    main()