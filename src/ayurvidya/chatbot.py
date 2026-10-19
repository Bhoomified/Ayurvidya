"""Real-time doubt-clearing chatbot.

The student's question is answered from (a) the shloka they are viewing, (b) its cached 7-step analysis,
and (c) a fresh hybrid retrieval over the whole knowledge base. Every answer comes back with the chunk ids it
cites, so the UI can show sources and the evaluation can measure faithfulness.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from .llm import LLM
from .pipeline import STEP_TITLES
from .retrieve import HybridRetriever
from .store import Store

NOT_FOUND = "I could not find this in the sources for this chapter."


@dataclass
class ChatAnswer:
    answer: str
    citations: list[str] = field(default_factory=list)   # chunk ids / step tags actually cited
    contexts: list[str] = field(default_factory=list)    # texts given to the model (for RAGAS)
    grounded: bool = True


class Chatbot:
    def __init__(self, retriever: HybridRetriever, llm: LLM, store: Store, prompts_dir: Path, k: int = 6):
        self.retriever, self.llm, self.store, self.k = retriever, llm, store, k
        self.system = (Path(prompts_dir) / "chatbot.md").read_text(encoding="utf-8")

    def ask(self, question: str, shloka_id: str | None = None, history: list[tuple[str, str]] | None = None) -> ChatAnswer:
        if not question or not question.strip():
            raise ValueError("empty question")
        parts, tags, contexts = [], {}, []
        if shloka_id:
            sh = self.store.shloka(shloka_id)
            if sh is None:
                raise KeyError(f"unknown shloka '{shloka_id}'")
            parts.append(f"CURRENT SHLOKA ({shloka_id}):\n{sh['text']}\n")
            for n, d in self.store.steps(shloka_id).items():
                parts.append(f"[S{n}] {STEP_TITLES[n]}:\n{d['output']}\n")
                tags[f"S{n}"] = f"step:{shloka_id}:{n}"
                contexts.append(d["output"])
        hits = self.retriever.search(question, self.k, source_types=["mula", "commentary", "kosha", "dhatu",
                                                                     "grammar", "crosstext"])
        if hits:
            parts.append("REFERENCES:\n" + "\n".join(
                f"[R{i}] ({h.chunk.source_type} · {h.chunk.work})\n{h.chunk.text}" for i, h in enumerate(hits, 1)))
        for i, h in enumerate(hits, 1):
            tags[f"R{i}"] = h.chunk.id
            contexts.append(h.chunk.text)
        convo = "".join(f"STUDENT: {q}\nTUTOR: {a}\n" for q, a in (history or [])[-4:])
        user = "\n".join(parts) + (f"\nEARLIER IN THIS CHAT:\n{convo}" if convo else "") + f"\nSTUDENT QUESTION: {question}"
        answer = self.llm.complete(self.system, user)
        cited = [tags[t] for t in dict.fromkeys(re.findall(r"\[([RS]\d+)\]", answer)) if t in tags]
        grounded = bool(cited) or NOT_FOUND in answer
        return ChatAnswer(answer, cited, contexts, grounded)
