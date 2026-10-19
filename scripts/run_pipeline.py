"""Run the 7-step pipeline offline and cache the results.

    python scripts/run_pipeline.py --verses 3 4 5          # selected verses
    python scripts/run_pipeline.py --range 1 30            # first 30 verses
    python scripts/run_pipeline.py --all --force           # regenerate everything
    python scripts/run_pipeline.py --range 1 30 --export outputs/su_ni_1_generated.xlsx
"""
from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")   # Devanagari on Windows consoles

from ayurvidya.export import export_xlsx  # noqa: E402
from ayurvidya.ingest import load_mula  # noqa: E402
from ayurvidya.pipeline import neighbour_texts  # noqa: E402
from ayurvidya.service import build_app  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--verses", nargs="+")
    g.add_argument("--range", nargs=2, type=int, metavar=("FROM", "TO"))
    g.add_argument("--all", action="store_true")
    ap.add_argument("--force", action="store_true", help="ignore the cache")
    ap.add_argument("--steps", nargs="+", type=int, default=list(range(1, 8)))
    ap.add_argument("--export", default=None)
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    app = build_app()
    shlokas, _ = load_mula(app.settings.data_dir / "raw" / "niimh_su_ni_1_mula.json")

    def last(n: str) -> int:
        return int(n.split("-")[-1])

    if args.all:
        chosen = list(range(len(shlokas)))
    elif args.range:
        chosen = [i for i, s in enumerate(shlokas) if args.range[0] <= last(s.number) <= args.range[1]]
    else:
        chosen = [i for i, s in enumerate(shlokas) if s.number in args.verses or any(
            v in s.number.split("-") for v in args.verses)]
    if not chosen:
        sys.exit("no matching verses")

    t0, bad = time.time(), 0
    for i in chosen:
        sh = shlokas[i]
        res = app.orchestrator.run_shloka(sh, steps=args.steps, force=args.force,
                                          neighbours=neighbour_texts(shlokas, i))
        flags = " ".join(f"{n}{'✓' if r.valid else '✗'}" for n, r in res.items())
        bad += sum(not r.valid for r in res.values())
        print(f"{sh.id:14s} {flags}")
    print(f"done: {len(chosen)} verses in {time.time() - t0:.1f}s, {bad} step outputs still failing validation")
    if args.export:
        print("exported:", export_xlsx(app.store, "su.ni.1", args.export))


if __name__ == "__main__":
    main()
