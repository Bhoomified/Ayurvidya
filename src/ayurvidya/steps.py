"""The 7 Ayurvidya steps as data: what each step reads, how it builds its retrieval query,
and how its output is checked.

Retrieval routing (which knowledge each step needs) follows the project design document:
  grammar steps (2, 6)       -> kosha, dhatupatha, grammar notes
  meaning steps (3, 4, 5)    -> Dalhana / Gayadasa commentary, kosha
  implied meaning (7)        -> commentary + parallel passages in Charaka / Ashtanga Hridaya (tantra-samanvaya)
Every step also sees the shloka itself (pinned) and two examples of the same step on other verses.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from .schema import STEPS, Shloka
from .text import split_padas, strip_verse_markers

ORD = {1: "1st", 2: "2nd", 3: "3rd", 4: "4th"}
_DEV = re.compile(r"[ऀ-ॿ]")
_LAT = re.compile(r"[A-Za-z]")


# ------------------------------------------------------------------ deterministic step 1
def sampradanam(shloka: Shloka) -> str:
    """Step 1 needs no LLM: pada division follows from danda positions and syllable counts.
    Padya -> four labelled padas. Gadya -> progressive joining of padas (1, 1+2, 1+2+3, ...)."""
    if shloka.is_prose:
        lines = []
        for sent in [s for s in re.split(r"[॥।]\s*[०-९0-9]*\s*[॥।]?", shloka.text) if s.strip()]:
            words = sent.split()
            lines += [" ".join(words[:i]) for i in range(1, len(words) + 1)]
        return "\n".join(lines)
    padas = split_padas(shloka.text)
    out = [f"{ORD.get(i, f'{i}th')} पाद- {p}" for i, p in enumerate(padas, 1)]
    if shloka.variant:
        out.append("पाठान्तरम्: " + " | ".join(split_padas(shloka.variant)))
    return "\n".join(out)


# ------------------------------------------------------------------ validators
def _words(text: str) -> list[str]:
    return [w for w in strip_verse_markers(text).split() if _DEV.search(w)]


def v_step1(out: str, sh: Shloka, prev: dict) -> list[str]:
    if sh.is_prose:
        return [] if out.strip() else ["empty output"]
    n = len([l for l in out.splitlines() if "पाद" in l and not l.startswith("पाठान्तरम्")])
    return [] if n == 4 else [f"expected 4 padas, got {n}"]


_PV_LINE = re.compile(r"^\s*(\d+)\.\s*(\S+)\s*[—–-]\s*(सुबन्त|तिङन्त|अव्यय)\S*\s*(?:[—–-]\s*(.*))?$")


def v_step2(out: str, sh: Shloka, prev: dict) -> list[str]:
    issues, lines = [], [l for l in out.splitlines() if l.strip()]
    ok = [l for l in lines if _PV_LINE.match(l)]
    if len(ok) < len(lines):
        issues.append(f"{len(lines) - len(ok)} line(s) not in format 'N. pada — सुबन्त/तिङन्त/अव्यय — tags'")
    nums = [int(_PV_LINE.match(l).group(1)) for l in ok]
    if nums and nums != list(range(1, len(nums) + 1)):
        issues.append("padas are not numbered 1..N in order")
    if len(ok) < 0.6 * len(_words(sh.text)):
        issues.append(f"only {len(ok)} padas for {len(_words(sh.text))} written words — padas missing?")
    for l in ok:
        m = _PV_LINE.match(l)
        if m.group(3) in ("सुबन्त", "तिङन्त") and not (m.group(4) or "").strip():
            issues.append(f"no grammatical tags for '{m.group(2)}'")
    return issues


def v_step3(out: str, sh: Shloka, prev: dict) -> list[str]:
    issues = []
    if not _DEV.search(out):
        issues.append("anvaya must be in Devanagari")
    if re.search(r"सुबन्त|तिङन्त|विभक्ति", out):
        issues.append("anvaya must not contain grammar labels")
    if len([l for l in out.splitlines() if l.strip()]) > 4:
        issues.append("anvaya should be one sentence (two if two orderings)")
    return issues


def v_step4(out: str, sh: Shloka, prev: dict) -> list[str]:
    pairs = re.findall(r"([ऀ-ॿ()][^=|\n]*?)\s*=\s*([^|\n]+)", out)
    issues = []
    if len(pairs) < 2:
        issues.append("expected 'pada = meaning | pada = meaning ...'")
    eng = [m for _, m in pairs if _LAT.search(m)]
    if pairs and len(eng) < 0.8 * len(pairs):
        issues.append("meanings must be in English")
    tail = out.strip().splitlines()[-1] if out.strip() else ""
    if "=" in tail or not _LAT.search(tail):
        issues.append("must end with one plain English sentence giving the complete literal meaning")
    n_pada = len(re.findall(r"^\s*\d+\.", prev.get(2, ""), re.M))
    if n_pada and len(pairs) < 0.6 * n_pada:
        issues.append(f"{len(pairs)} meanings for {n_pada} padas — some padas skipped")
    return issues


def _sentences(text: str) -> int:
    return len([s for s in re.split(r"(?<=[.!?।])\s+", text.strip()) if len(s) > 3])


def v_step5(out: str, sh: Shloka, prev: dict) -> list[str]:
    n = _sentences(out)
    issues = [] if 2 <= n <= 6 else [f"bhavartha should be 2-5 sentences, got {n}"]
    if not _LAT.search(out):
        issues.append("bhavartha must be in English")
    return issues


def v_step6(out: str, sh: Shloka, prev: dict) -> list[str]:
    blocks = re.split(r"(?m)^\s*पद\s*:", out)[1:]
    if not blocks:
        return ["no 'पद:' blocks found"]
    need = ("Grammar:", "धातु", "Contribution:")
    return [f"block {i} missing '{k}'" for i, b in enumerate(blocks, 1) for k in need if k not in b]


def v_step7(out: str, sh: Shloka, prev: dict) -> list[str]:
    n = _sentences(out)
    issues = [] if 2 <= n <= 5 else [f"dhvanitartha should be 2-4 sentences, got {n}"]
    for k in (2, 5):   # must not merely repeat earlier layers
        if prev.get(k) and out.strip()[:80] == prev[k].strip()[:80]:
            issues.append(f"repeats step {k} instead of giving the implied meaning")
    return issues


# ------------------------------------------------------------------ step specs
@dataclass
class StepSpec:
    number: int
    name: str
    prompt_file: str
    source_types: tuple[str, ...]
    k: int
    validator: Callable[[str, Shloka, dict], list[str]]
    uses_llm: bool = True
    query: Callable[[Shloka, dict], str] = field(default=lambda sh, prev: strip_verse_markers(sh.text))
    prev_steps: tuple[int, ...] = ()

    def prompt(self, prompts_dir: Path) -> tuple[str, str]:
        """(system prompt, version hash). The hash goes into the cache key, so editing a prompt
        automatically invalidates its cached outputs."""
        body = (Path(prompts_dir) / self.prompt_file).read_text(encoding="utf-8")
        body = re.sub(r"<!--.*?-->\s*", "", body, flags=re.S)
        common = (Path(prompts_dir) / "_grounding.md").read_text(encoding="utf-8")
        system = body.strip() + "\n\n" + common.strip()
        return system, hashlib.sha1(system.encode("utf-8")).hexdigest()[:10]


def _q_words(sh: Shloka, prev: dict) -> str:
    padas = re.findall(r"^\s*\d+\.\s*(\S+)", prev.get(2, ""), re.M)
    return " ".join(padas) or strip_verse_markers(sh.text)


STEP_SPECS: dict[int, StepSpec] = {
    1: StepSpec(1, STEPS[1], "step1_sampradanam.md", ("mula",), 1, v_step1, uses_llm=False),
    2: StepSpec(2, STEPS[2], "step2_padavibhaga.md", ("mula", "commentary", "kosha", "grammar", "gold"), 8,
                v_step2, prev_steps=(1,)),
    3: StepSpec(3, STEPS[3], "step3_anvaya.md", ("mula", "commentary", "gold"), 6, v_step3, prev_steps=(1, 2)),
    4: StepSpec(4, STEPS[4], "step4_anvayartha.md", ("mula", "commentary", "kosha", "gold"), 8, v_step4,
                query=_q_words, prev_steps=(2, 3)),
    5: StepSpec(5, STEPS[5], "step5_bhavartha.md", ("mula", "commentary", "crosstext", "gold"), 8, v_step5,
                prev_steps=(3, 4)),
    6: StepSpec(6, STEPS[6], "step6_padakrityam.md", ("mula", "commentary", "kosha", "dhatu", "grammar", "gold"),
                10, v_step6, query=_q_words, prev_steps=(2, 4)),
    7: StepSpec(7, STEPS[7], "step7_dhvanitartha.md", ("mula", "commentary", "crosstext", "grammar", "gold"), 8,
                v_step7, prev_steps=(4, 5, 6)),
}
