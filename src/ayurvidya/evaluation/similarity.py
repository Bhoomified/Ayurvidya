"""How close is the AI's output to the scholar's gold answer? (automatic, before the human CVI rating)

chrF = character n-gram F-score (Popović 2015). It works well for Sanskrit and Devanagari because it
compares pieces of words, so a small sandhi or ending difference costs a little, not the whole word.
0 = nothing in common, 100 = identical. It is only a screening number - the scholars' CVI is the real test.
"""
from __future__ import annotations

import re
import unicodedata
from collections import Counter


def _clean(text: str) -> str:
    t = unicodedata.normalize("NFC", text or "")
    t = t.replace("||", "॥").replace("|", "।")
    return re.sub(r"\s+", " ", t).strip()


def _ngrams(text: str, n: int) -> Counter:
    t = text.replace(" ", "")
    return Counter(t[i:i + n] for i in range(len(t) - n + 1))


def chrf(hypothesis: str, reference: str, max_n: int = 6, beta: float = 2.0) -> float:
    """chrF score in [0, 100]. beta=2 weights recall (covering the gold content) twice as much as precision."""
    hyp, ref = _clean(hypothesis), _clean(reference)
    if not hyp or not ref:
        return 100.0 if hyp == ref else 0.0
    precs, recs = [], []
    for n in range(1, max_n + 1):
        h, r = _ngrams(hyp, n), _ngrams(ref, n)
        if not h or not r:
            continue
        overlap = sum((h & r).values())
        precs.append(overlap / sum(h.values()))
        recs.append(overlap / sum(r.values()))
    if not precs:
        return 0.0
    p, r = sum(precs) / len(precs), sum(recs) / len(recs)
    if p == 0 and r == 0:
        return 0.0
    b2 = beta * beta
    return round(100 * (1 + b2) * p * r / (b2 * p + r), 2)