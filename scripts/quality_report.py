"""Quality of the generated outputs, before the scholars rate them.

    python scripts/quality_report.py                  # prints + saves outputs/quality_report.md

1. Format check: share of outputs per step that passed the validator, and the commonest problems.
2. Closeness to gold (verses 1-30): chrF score of AI output vs the scholar-validated table, per step.
   The AI never saw a verse's own gold row while generating it (leakage guard), so this is a fair check.
3. The 10 weakest outputs - review these first.
"""
from __future__ import annotations

import sys
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from ayurvidya.config import load_settings  # noqa: E402
from ayurvidya.evaluation.similarity import chrf  # noqa: E402
from ayurvidya.ingest import load_gold_xlsx  # noqa: E402
from ayurvidya.schema import STEPS  # noqa: E402
from ayurvidya.store import Store  # noqa: E402


def main() -> None:
    s = load_settings()
    store = Store(s.db_path)
    gold: dict[str, dict[int, str]] = {}
    for g in sorted((s.data_dir / "gold").glob("*.xlsx")):
        gold.update(load_gold_xlsx(g))

    valid, total, problems = Counter(), Counter(), Counter()
    scores: dict[int, list[float]] = defaultdict(list)
    weakest = []
    shl = store.shlokas("su.ni.1")
    done = 0
    for sh in shl:
        steps = store.steps(sh["id"])
        done += len(steps) == 7
        for n, d in steps.items():
            total[n] += 1
            valid[n] += d["valid"]
            for issue in d["issues"]:
                problems[f"step {n}: {issue[:70]}"] += 1
            ref = gold.get(sh["id"], {}).get(n)
            if ref and n > 1:
                sc = chrf(d["output"], ref)
                scores[n].append(sc)
                weakest.append((sc, sh["id"], n))

    lines = ["# Quality report", "", f"- model(s): {', '.join(sorted(m for m in models(store)))}",
             f"- verses with all 7 steps: **{done}/{len(shl)}**", "",
             "## 1. Format check and closeness to gold", "",
             "| step | outputs | passed format check | chrF vs gold (verses with gold) |", "| --- | --- | --- | --- |"]
    for n in range(1, 8):
        if not total[n]:
            continue
        g = f"{mean(scores[n]):.1f}  (n={len(scores[n])})" if scores[n] else "—"
        lines.append(f"| {n} {STEPS[n]} | {total[n]} | {100 * valid[n] / total[n]:.0f}% | {g} |")
    lines += ["", "chrF: 0-100, higher = closer to the scholar's answer. Rough guide for Sanskrit: "
              "60+ close, 40-60 partly right, <40 check carefully.", "",
              "## 2. Commonest format problems", ""]
    lines += [f"- {k} — {v}x" for k, v in problems.most_common(10)] or ["- none"]
    lines += ["", "## 3. Weakest outputs vs gold (review these first)", ""]
    lines += [f"- {sid} step {n} ({STEPS[n]}): chrF {sc}" for sc, sid, n in sorted(weakest)[:10]] or ["- no gold overlap yet"]

    report = "\n".join(lines)
    print(report)
    out = ROOT / "outputs" / "quality_report.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(report + "\n", encoding="utf-8")
    print(f"\nsaved to {out.relative_to(ROOT)}")
    store.close()


def models(store: Store) -> set[str]:
    return {r[0] for r in store.db.execute("SELECT DISTINCT model FROM shloka_steps")}


if __name__ == "__main__":
    main()