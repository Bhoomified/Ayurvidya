"""RAGAS-style, reference-free checks of chatbot answers (Es et al., EACL 2024 demo), implemented directly
on our LLM client so they work with any provider and do not break when the ragas package changes.

  faithfulness       = supported claims / all claims in the answer      (LLM splits + verifies claims)
  answer_relevance   = mean cosine(question, questions regenerated from the answer)
  context_precision  = share of retrieved contexts the judge marks as needed for the answer

For the paper, report these next to the official `ragas` library numbers when it is available.
"""
from __future__ import annotations

import json
import re

import numpy as np

CLAIMS_PROMPT = ("Split the ANSWER into short, self-contained factual claims. Return a JSON list of strings only.")
VERIFY_PROMPT = ("For each CLAIM decide if it can be directly inferred from the CONTEXT. Return a JSON list of "
                 "1 (supported) or 0 (not supported), one per claim, nothing else.")
QGEN_PROMPT = ("Write {n} different questions that the ANSWER answers. Return a JSON list of strings only.")
NEED_PROMPT = ("For each numbered CONTEXT passage, return 1 if it is needed to answer the QUESTION, else 0. "
               "Return a JSON list of 0/1 only.")


def _json_list(text: str) -> list:
    m = re.search(r"\[.*\]", text, re.S)
    if not m:
        return []
    try:
        v = json.loads(m.group(0))
        return v if isinstance(v, list) else []
    except json.JSONDecodeError:
        return []


def faithfulness(llm, answer: str, contexts: list[str]) -> float | None:
    claims = [c for c in _json_list(llm.complete(CLAIMS_PROMPT, f"ANSWER:\n{answer}")) if isinstance(c, str)]
    if not claims:
        return None
    ctx = "\n\n".join(contexts)
    verdicts = _json_list(llm.complete(VERIFY_PROMPT, f"CONTEXT:\n{ctx}\n\nCLAIMS:\n" + json.dumps(claims, ensure_ascii=False)))
    if len(verdicts) != len(claims):
        return None
    return sum(int(v) == 1 for v in verdicts) / len(claims)


def answer_relevance(llm, embedder, question: str, answer: str, n: int = 3) -> float | None:
    qs = [q for q in _json_list(llm.complete(QGEN_PROMPT.format(n=n), f"ANSWER:\n{answer}")) if isinstance(q, str)]
    if not qs:
        return None
    qv = embedder.embed_query(question)
    gv = np.stack([embedder.embed_query(q) for q in qs])
    return float(np.mean(gv @ qv))


def context_precision(llm, question: str, contexts: list[str]) -> float | None:
    if not contexts:
        return None
    listing = "\n".join(f"{i}. {c[:600]}" for i, c in enumerate(contexts, 1))
    v = _json_list(llm.complete(NEED_PROMPT, f"QUESTION: {question}\n\nCONTEXT:\n{listing}"))
    if len(v) != len(contexts):
        return None
    return sum(int(x) == 1 for x in v) / len(v)
