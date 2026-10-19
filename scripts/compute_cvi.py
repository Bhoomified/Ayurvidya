"""Compute I-CVI / S-CVI / modified kappa from the scholars' rating sheet.

Rating sheet (CSV, one row per item, one column per expert):
    item,expert1,expert2,expert3,expert4,expert5,expert6
    su.ni.1.3:1,4,4,3,4,4,3
    su.ni.1.3:2,3,4,4,2,4,4
    ...
Item id = <shloka id>:<step number>.

    python scripts/compute_cvi.py data/eval/cvi_ratings.csv
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")   # Devanagari on Windows consoles

from ayurvidya.evaluation.cvi import by_step, cvi_report  # noqa: E402


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    with open(sys.argv[1], encoding="utf-8") as f:
        rows = list(csv.reader(f))
    items = {r[0]: [int(x) for x in r[1:] if x.strip()] for r in rows[1:] if r}
    rep = cvi_report(items)
    print(json.dumps({"s_cvi_ave": rep["s_cvi_ave"], "s_cvi_ua": rep["s_cvi_ua"],
                      "mean_i_cvi_by_step": by_step(items),
                      "items_below_0.78": [k for k, v in rep["items"].items() if not v["meets_0.78"]]},
                     indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
