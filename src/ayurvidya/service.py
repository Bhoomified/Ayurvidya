"""Wires settings -> knowledge base -> retriever -> LLM -> store -> orchestrator/chatbot.
Both the scripts and the API create the app through `build_app()`, so they always agree."""
from __future__ import annotations

from dataclasses import dataclass

from .chatbot import Chatbot
from .config import Settings, load_settings
from .index import KnowledgeBase
from .llm import make_llm
from .pipeline import Orchestrator
from .retrieve import HybridRetriever, Reranker, RetrievalConfig
from .store import Store


@dataclass
class App:
    settings: Settings
    kb: KnowledgeBase
    retriever: HybridRetriever
    store: Store
    orchestrator: Orchestrator
    chatbot: Chatbot


def build_app(settings: Settings | None = None, llm=None) -> App:
    s = settings or load_settings()
    kb = KnowledgeBase.load(s.kb_dir)
    reranker = Reranker(s.reranker.split(":", 1)[1]) if s.reranker.startswith("bge:") else None
    retriever = HybridRetriever(kb, RetrievalConfig(s.dense_k, s.sparse_k, s.rrf_k, s.final_k), reranker)
    llm = llm or make_llm(s.llm, s.llm_base_url, s.temperature, s.max_tokens)
    store = Store(s.db_path)
    orch = Orchestrator(retriever, llm, store, s.prompts_dir, s.max_retries)
    bot = Chatbot(retriever, llm, store, s.prompts_dir, k=s.final_k)
    return App(s, kb, retriever, store, orch, bot)
