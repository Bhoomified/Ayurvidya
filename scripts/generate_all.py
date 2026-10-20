"""Generate the 7 steps for the whole chapter, safely, in small batches (free-tier friendly).

    python scripts/generate_all.py --limit 10            # next 10 verses that are not done yet
    python scripts/generate_all.py --limit 10 --pause 6  # wait 6 s between AI calls (free-tier limits)
    python scripts/generate_all.py --status              # how many verses are done, nothing generated

- Resumable: verses whose 7 steps are already saved (same prompt + same model) are skipped, so you can stop
  any time (Ctrl+C) and run again tomorrow. Scholar-approved steps are never regenerated.
- One verse failing (network, quota) does not stop the run; after 3 failures in a row it stops
  (usually the daily quota is used up - try again later).
- Makes a database backup first. Every verse is logged in outputs/generation_log.csv.
"""
from __future__ import annotations

import argparse
import csv
import logging
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from ayurvidya.ingest import load_mula  # noqa: E402
from ayurvidya.pipeline import neighbour_texts  # noqa: E402
from ayurvidya.service import build_app  # noqa: E402
from ayurvidya.steps import STEP_SPECS  # noqa: E402

LOG = ROOT / "outputs" / "generation_log.csv"


class PacedLLM:
    """Wraps the real model and waits `pause` seconds between calls, to stay under free-tier rate limits.
    Keeps the same .name, so the cache still recognises earlier outputs."""

    def __init__(self, inner, pause: float):
        self.inner, self.pause, self._last = inner, pause, 0.0
        self.name = inner.name
        self.calls = 0

    def complete(self, system: str, user: str) -> str:
        wait = self._last + self.pause - time.time()
        if wait > 0:
            time.sleep(wait)
        try:
            return self.inner.complete(system, user)
        finally:
            self._last = time.time()
            self.calls += 1


def is_done(app, sh) -> bool:
    """True if all 7 steps are cached for the current prompts + model (or approved)."""
    for n, spec in STEP_SPECS.items():
        _, version = spec.prompt(app.settings.prompts_dir)
        model = app.orchestrator.llm.name if spec.uses_llm else "rule-based"
        if not app.store.cached(sh.id, n, version, model):
            return False
    return True


def log_row(row: dict) -> None:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    new = not LOG.exists()
    with open(LOG, "a", encoding="utf-8-sig" if new else "utf-8", newline="") as f:
        w = csv.DictWriter(f, ["time", "shloka_id", "model", "result", "steps_valid", "ai_calls", "seconds", "error"])
        if new:
            w.writeheader()
        w.writerow(row)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=10, help="max verses to generate in this run")
    ap.add_argument("--pause", type=float, default=4.0, help="seconds between AI calls (0 for paid / local)")
    ap.add_argument("--status", action="store_true")
    args = ap.parse_args()
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(message)s")

    app = build_app()
    if app.orchestrator.llm.name == "mock" and not args.status:
        sys.exit("AYV_LLM is 'mock'. Set the real model in .env first (python scripts/check_llm.py).")
    shlokas, _ = load_mula(app.settings.data_dir / "raw" / "niimh_su_ni_1_mula.json")
    todo = [i for i, sh in enumerate(shlokas) if not is_done(app, sh)]
    print(f"model: {app.orchestrator.llm.name}   done: {len(shlokas) - len(todo)}/{len(shlokas)} verses")
    if args.status or not todo:
        return

    sys.path.insert(0, str(ROOT / "scripts"))
    from backup_db import backup
    print("backup:", backup(app.settings.db_path).name)

    llm = PacedLLM(app.orchestrator.llm, args.pause)
    app.orchestrator.llm = llm
    fails_in_row, t_all = 0, time.time()
    for i in todo[:args.limit]:
        sh, t0, calls0 = shlokas[i], time.time(), llm.calls
        row = {"time": f"{datetime.now():%Y-%m-%d %H:%M}", "shloka_id": sh.id, "model": llm.name, "error": ""}
        try:
            res = app.orchestrator.run_shloka(sh, neighbours=neighbour_texts(shlokas, i))
            ok = sum(r.valid for r in res.values())
            row.update(result="ok", steps_valid=f"{ok}/7")
            print(f"{sh.id:14s} " + " ".join(f"{n}{'✓' if r.valid else '✗'}" for n, r in res.items()))
            fails_in_row = 0
        except Exception as e:      # network / quota / server error: log it and go on
            row.update(result="FAILED", steps_valid="", error=str(e)[:300])
            print(f"{sh.id:14s} FAILED: {str(e)[:150]}")
            fails_in_row += 1
        row.update(ai_calls=llm.calls - calls0, seconds=round(time.time() - t0, 1))
        log_row(row)
        if fails_in_row >= 3:
            print("\n3 failures in a row - stopping (daily quota used up or network down). Run again later.")
            break
    left = sum(not is_done(app, sh) for sh in shlokas)
    print(f"\n{llm.calls} AI calls in {time.time() - t_all:.0f}s.  Still to do: {left} verses.  Log: {LOG.relative_to(ROOT)}")


if __name__ == "__main__":
    main()