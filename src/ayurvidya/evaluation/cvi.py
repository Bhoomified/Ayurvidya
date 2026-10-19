"""Content Validity Index for expert ratings of the 7-step outputs.

Experts rate each item (one step output of one shloka) on a 4-point relevance scale:
1 = not relevant, 2 = somewhat relevant, 3 = quite relevant, 4 = highly relevant.

  I-CVI      = (# experts rating 3 or 4) / (# experts)                     target >= 0.78 with >= 6 experts
  S-CVI/Ave  = mean of the I-CVIs                                          target >= 0.90
  S-CVI/UA   = share of items that ALL experts rated 3 or 4
  modified kappa k* = (I-CVI - Pc) / (1 - Pc),  Pc = C(N, A) * 0.5**N     (adjusts I-CVI for chance)
                k* > 0.74 excellent, 0.60-0.74 good, 0.40-0.59 fair

References: Lynn (1986) Nursing Research 35(6); Polit & Beck (2006) Res Nurs Health 29(5);
Polit, Beck & Owen (2007) Res Nurs Health 30(4).
"""
from __future__ import annotations

from math import comb


def i_cvi(ratings: list[int]) -> float:
    if not ratings:
        raise ValueError("no ratings")
    if any(r not in (1, 2, 3, 4) for r in ratings):
        raise ValueError("ratings must be 1-4")
    return sum(r >= 3 for r in ratings) / len(ratings)


def modified_kappa(ratings: list[int]) -> float:
    n, a = len(ratings), sum(r >= 3 for r in ratings)
    pc = comb(n, a) * 0.5 ** n
    icvi = a / n
    return (icvi - pc) / (1 - pc) if pc < 1 else 0.0


def kappa_label(k: float) -> str:
    return "excellent" if k > 0.74 else "good" if k >= 0.60 else "fair" if k >= 0.40 else "poor"


def cvi_report(items: dict[str, list[int]]) -> dict:
    """items: {item_id: [rating by expert 1, expert 2, ...]} -> per-item and scale-level indices."""
    per = {}
    for item, rs in items.items():
        k = modified_kappa(rs)
        per[item] = {"i_cvi": round(i_cvi(rs), 3), "kappa": round(k, 3), "label": kappa_label(k),
                     "n_experts": len(rs), "meets_0.78": i_cvi(rs) >= 0.78}
    vals = [v["i_cvi"] for v in per.values()]
    return {"items": per,
            "s_cvi_ave": round(sum(vals) / len(vals), 3) if vals else None,
            "s_cvi_ua": round(sum(v == 1.0 for v in vals) / len(vals), 3) if vals else None}


def by_step(items: dict[str, list[int]]) -> dict[int, float]:
    """Item ids look like 'su.ni.1.3:5' (shloka:step). Returns the mean I-CVI per step,
    which shows which of the 7 steps the system does well or badly."""
    acc: dict[int, list[float]] = {}
    for item, rs in items.items():
        step = int(item.rsplit(":", 1)[1])
        acc.setdefault(step, []).append(i_cvi(rs))
    return {s: round(sum(v) / len(v), 3) for s, v in sorted(acc.items())}
