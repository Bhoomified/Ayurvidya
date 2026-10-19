"""The orchestrator: runs the 7 step agents in order for one shloka, passing each step's output to the
next, validating every output and re-asking with the specific problems when it fails.

    for step in 1..7:
        cached & still valid?      -> reuse
        step 1                     -> deterministic (no LLM)
        else: context = pinned (this verse's mula + commentary) + hybrid search (step's sources)
              + 2 same-step examples from OTHER verses + earlier step outputs
              output = LLM(system = step prompt + grounding rules, user = context)
              issues = validator(output); retry up to max_retries with the issues listed
        save to cache (with retrieved chunk ids, model, prompt hash)
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from .llm import LLM
from .retrieve import HybridRetriever
from .schema import STEPS, Hit, Shloka, StepResult
from .steps import STEP_SPECS, StepSpec, sampradanam
from .store import Store

log = logging.getLogger("ayurvidya.pipeline")

STEP_TITLES = {1: "संप्रदानम् (Sampradanam)", 2: "पदविभागः (Padavibhaga)", 3: "अन्वयः (Anvaya)",
               4: "अन्वयार्थः (Anvayartha)", 5: "भावार्थः (Bhavartha)", 6: "पदकृत्यम् (Padakrityam)",
               7: "ध्वनितार्थः (Dhvanitartha)"}


def format_context(spec: StepSpec, sh: Shloka, prev: dict[int, str], hits: list[Hit],
                   neighbours: tuple[str, str] = ("", "")) -> str:
    """The user message for one step. Reference tags [R1].. let the model cite and let us audit."""
    parts = [f"TASK: step {spec.number} — {STEP_TITLES[spec.number]}",
             f"SHLOKA ({sh.id}, Sushruta Samhita, Nidana Sthana {sh.chapter}, verse {sh.number}):\n{sh.text}\n"]
    if sh.variant:
        parts.append(f"VARIANT READING printed by NIIMH (for reference only):\n{sh.variant}\n")
    if any(neighbours):
        parts.append(f"CONTEXT (prakarana): previous verse: {neighbours[0] or '—'}\nnext verse: {neighbours[1] or '—'}\n")
    for k in spec.prev_steps:
        if prev.get(k):
            parts.append(f"OUTPUT OF STEP {k} — {STEP_TITLES[k]}:\n{prev[k]}\n")
    refs = [h for h in hits if h.chunk.source_type != "gold"]
    exs = [h for h in hits if h.chunk.source_type == "gold"]
    if refs:
        parts.append("REFERENCES:\n" + "\n".join(
            f"[R{i}] ({h.chunk.source_type} · {h.chunk.work}{' · ' + ','.join(h.chunk.shloka_ids) if h.chunk.shloka_ids else ''})\n{h.chunk.text}"
            for i, h in enumerate(refs, 1)) + "\n")
    if exs:
        parts.append("EXAMPLES (same step, other verses — copy the format only):\n" + "\n".join(
            f"[E{i}] ({','.join(h.chunk.shloka_ids)})\n{h.chunk.text}" for i, h in enumerate(exs, 1)) + "\n")
    parts.append(f"Now write step {spec.number} for the SHLOKA above, in the exact OUTPUT FORMAT.")
    return "\n".join(parts)


@dataclass
class Orchestrator:
    retriever: HybridRetriever
    llm: LLM
    store: Store
    prompts_dir: Path
    max_retries: int = 2

    def run_shloka(self, sh: Shloka, steps=range(1, 8), force: bool = False,
                   neighbours: tuple[str, str] = ("", "")) -> dict[int, StepResult]:
        prev: dict[int, str] = {n: d["output"] for n, d in self.store.steps(sh.id).items()}
        results: dict[int, StepResult] = {}
        for n in steps:
            spec = STEP_SPECS[n]
            res = self.run_step(spec, sh, prev, force=force, neighbours=neighbours)
            results[n] = res
            prev[n] = res.output
        return results

    def run_step(self, spec: StepSpec, sh: Shloka, prev: dict[int, str], force: bool = False,
                 neighbours: tuple[str, str] = ("", "")) -> StepResult:
        system, version = spec.prompt(self.prompts_dir)
        model = self.llm.name if spec.uses_llm else "rule-based"
        if not force:
            hit = self.store.cached(sh.id, spec.number, version, model)
            if hit:
                return StepResult(sh.id, spec.number, hit["output"], bool(hit["valid"]),
                                  model=hit["model"], prompt_version=hit["prompt_version"], attempts=0)
        if not spec.uses_llm:
            out = sampradanam(sh)
            res = StepResult(sh.id, spec.number, out, not spec.validator(out, sh, prev),
                             spec.validator(out, sh, prev), [], model, version)
            self.store.save_step(res)
            return res

        hits = self.retriever.context_for_step(sh.id, spec.query(sh, prev), spec.source_types, spec.k,
                                               step=spec.number)
        user = format_context(spec, sh, prev, hits, neighbours)
        out, issues, attempt = "", ["not run"], 0
        for attempt in range(1, self.max_retries + 2):
            out = self.llm.complete(system, user)
            issues = spec.validator(out, sh, prev)
            if not issues:
                break
            log.info("%s step %d attempt %d issues: %s", sh.id, spec.number, attempt, issues)
            user = (format_context(spec, sh, prev, hits, neighbours) +
                    "\n\nYOUR PREVIOUS ANSWER HAD THESE PROBLEMS — fix them and answer again in the exact format:\n- "
                    + "\n- ".join(issues) + f"\n\nPREVIOUS ANSWER:\n{out}")
        res = StepResult(sh.id, spec.number, out, not issues, issues, [h.chunk.id for h in hits],
                         model, version, attempt)
        self.store.save_step(res)
        return res


def neighbour_texts(shlokas: list[Shloka], i: int) -> tuple[str, str]:
    return (shlokas[i - 1].text if i > 0 else "", shlokas[i + 1].text if i + 1 < len(shlokas) else "")


__all__ = ["Orchestrator", "format_context", "neighbour_texts", "STEP_TITLES", "STEPS"]
