"""Learning-gain statistics (pre-test vs post-test, same students) and usability scores.

paired_test(): Shapiro-Wilk on the differences decides the test —
  normal (p >= 0.05)  -> paired t-test, effect size Cohen's d_z = mean(diff) / sd(diff)
  not normal          -> Wilcoxon signed-rank, effect size r = Z / sqrt(n)
Significance threshold p < 0.05 (two-sided), as fixed in the synopsis.
"""
from __future__ import annotations

import math

import numpy as np
from scipy import stats


def paired_test(pre: list[float], post: list[float], alpha: float = 0.05) -> dict:
    pre_a, post_a = np.asarray(pre, float), np.asarray(post, float)
    if pre_a.shape != post_a.shape or pre_a.size < 3:
        raise ValueError("pre and post must be paired lists with at least 3 students")
    diff = post_a - pre_a
    sw_p = float(stats.shapiro(diff).pvalue) if diff.size >= 3 and np.ptp(diff) > 0 else 0.0
    out = {"n": int(diff.size), "mean_pre": float(pre_a.mean()), "mean_post": float(post_a.mean()),
           "mean_gain": float(diff.mean()), "shapiro_p": sw_p}
    if sw_p >= alpha:
        t = stats.ttest_rel(post_a, pre_a)
        sd = float(diff.std(ddof=1))
        out.update(test="paired t-test", statistic=float(t.statistic), p=float(t.pvalue),
                   effect_size=float(diff.mean() / sd) if sd else math.inf, effect="Cohen's d_z")
    else:
        w = stats.wilcoxon(post_a, pre_a, zero_method="wilcox", method="approx")
        z = float(getattr(w, "zstatistic", np.nan))
        if math.isnan(z):   # older SciPy: recover |Z| from the two-sided p-value
            z = float(stats.norm.isf(w.pvalue / 2))
        out.update(test="Wilcoxon signed-rank", statistic=float(w.statistic), p=float(w.pvalue),
                   effect_size=abs(z) / math.sqrt(diff.size), effect="r = Z/sqrt(n)")
    out["significant"] = out["p"] < alpha
    return out


def normalized_gain(pre: float, post: float, max_score: float) -> float:
    """Hake's normalised gain g = (post - pre) / (max - pre): share of the possible improvement achieved."""
    return (post - pre) / (max_score - pre) if max_score > pre else 0.0


def sus_score(answers: list[int]) -> float:
    """System Usability Scale (Brooke, 1996): 10 items on 1-5.
    Odd items contribute (x - 1), even items (5 - x); the sum x 2.5 gives 0-100. 68 = average."""
    if len(answers) != 10 or any(a not in (1, 2, 3, 4, 5) for a in answers):
        raise ValueError("SUS needs 10 answers on a 1-5 scale")
    return 2.5 * sum((a - 1) if i % 2 == 0 else (5 - a) for i, a in enumerate(answers))


def mars_section_means(scores: dict[str, list[int]]) -> dict[str, float]:
    """Mobile App Rating Scale (Stoyanov et al., 2015): items 1-5 grouped into sections
    (engagement, functionality, aesthetics, information, subjective). Returns the mean per section and
    the app-quality mean (mean of the four objective sections A-D)."""
    means = {s: round(float(np.mean(v)), 2) for s, v in scores.items()}
    obj = [means[s] for s in ("engagement", "functionality", "aesthetics", "information") if s in means]
    if obj:
        means["app_quality_mean"] = round(float(np.mean(obj)), 2)
    return means
