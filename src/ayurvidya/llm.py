"""LLM clients behind one method: complete(system, user) -> str.

  anthropic:<model>   Claude via the Messages API (needs ANTHROPIC_API_KEY)
  openai:<model>      any OpenAI-compatible endpoint: OpenAI, Ollama (http://localhost:11434/v1),
                      vLLM, LM Studio, Groq ... (key in OPENAI_API_KEY; base URL in settings.llm_base_url)
  mock                deterministic offline stub used by the test-suite

Only `requests` is used, so no vendor SDK is required. Calls retry with exponential back-off on
rate limits (429) and server errors (5xx).
"""
from __future__ import annotations

import os
import re
import time
from typing import Callable, Protocol

import requests


class LLM(Protocol):
    name: str
    def complete(self, system: str, user: str) -> str: ...


class LLMError(RuntimeError):
    pass


def _post_with_retry(url: str, headers: dict, payload: dict, tries: int = 5, timeout: int = 120) -> dict:
    delay = 2.0
    for attempt in range(1, tries + 1):
        try:
            r = requests.post(url, headers=headers, json=payload, timeout=timeout)
        except requests.RequestException as e:
            if attempt == tries:
                raise LLMError(f"network error: {e}") from e
        else:
            if r.status_code == 200:
                return r.json()
            if r.status_code not in (429, 500, 502, 503, 504, 529) or attempt == tries:
                raise LLMError(f"HTTP {r.status_code}: {r.text[:500]}")
        time.sleep(delay)
        delay *= 2
    raise LLMError("unreachable")


class AnthropicLLM:
    URL = "https://api.anthropic.com/v1/messages"

    def __init__(self, model: str, temperature: float = 0.0, max_tokens: int = 2000):
        self.key = os.environ.get("ANTHROPIC_API_KEY")
        if not self.key:
            raise LLMError("Set ANTHROPIC_API_KEY in your environment (.env)")
        self.name, self.model, self.temperature, self.max_tokens = f"anthropic:{model}", model, temperature, max_tokens

    def complete(self, system: str, user: str) -> str:
        data = _post_with_retry(self.URL, {
            "x-api-key": self.key, "anthropic-version": "2023-06-01", "content-type": "application/json",
        }, {
            "model": self.model, "max_tokens": self.max_tokens, "temperature": self.temperature,
            # the system prompt is identical across verses for a step, so it is cached server-side
            "system": [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
            "messages": [{"role": "user", "content": user}],
        })
        return "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text").strip()


class OpenAICompatLLM:
    def __init__(self, model: str, base_url: str = "", temperature: float = 0.0, max_tokens: int = 2000):
        self.base = (base_url or "https://api.openai.com/v1").rstrip("/")
        self.key = os.environ.get("OPENAI_API_KEY", "not-needed-for-local")
        self.name, self.model, self.temperature, self.max_tokens = f"openai:{model}", model, temperature, max_tokens

    def complete(self, system: str, user: str) -> str:
        data = _post_with_retry(f"{self.base}/chat/completions", {
            "Authorization": f"Bearer {self.key}", "Content-Type": "application/json",
        }, {
            "model": self.model, "temperature": self.temperature, "max_tokens": self.max_tokens,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        })
        return data["choices"][0]["message"]["content"].strip()


class MockLLM:
    """Offline stand-in. Produces format-valid output for each step so the whole pipeline, cache,
    API and evaluation code can be tested without a key. `responder` overrides the default."""
    name = "mock"

    def __init__(self, responder: Callable[[str, str], str] | None = None):
        self.responder = responder
        self.calls: list[tuple[str, str]] = []

    def complete(self, system: str, user: str) -> str:
        self.calls.append((system, user))
        if self.responder:
            return self.responder(system, user)
        m = re.search(r"TASK: step (\d)", user)
        step = int(m.group(1)) if m else 0
        sh = re.search(r"SHLOKA[^\n]*\n(.+?)\n\n", user, re.S)
        words = re.findall(r"[ऀ-ॿ]+", sh.group(1) if sh else "")
        words = [w for w in words if not re.fullmatch(r"[।॥०-९]+", w)][:8] or ["पदम्"]
        if step == 2:
            return "\n".join(f"{i}. {w} — सुबन्त — पुं., प्रथमा, एकवचनम्" for i, w in enumerate(words, 1))
        if step == 3:
            return " ".join(words) + "।"
        if step == 4:
            return " | ".join(f"{w} = meaning of {w}" for w in words) + "\nThe verse states its literal sense [R1]."
        if step == 5:
            return "The author introduces the topic of this verse [R1]. It fits the chapter on Vata disorders."
        if step == 6:
            return (f"पद: {words[0]}\nSynonyms: —\nGrammar: सुबन्त\nधातु: — | धात्वर्थ: —\nउपसर्ग: —\n"
                    f"Contribution: Its form adds emphasis.")
        if step == 7:
            return "The wording hints at a deeper intent of the Acharya [R1]. It links to parallel texts."
        if step == 0:   # chatbot / judge calls
            return "Based on the references [R1], the verse explains this point."
        return "1st पाद- " + " ".join(words[:2])


def make_llm(spec: str, base_url: str = "", temperature: float = 0.0, max_tokens: int = 2000) -> LLM:
    if spec == "mock":
        return MockLLM()
    provider, _, model = spec.partition(":")
    if provider == "anthropic":
        return AnthropicLLM(model, temperature, max_tokens)
    if provider == "openai":
        return OpenAICompatLLM(model, base_url, temperature, max_tokens)
    raise ValueError(f"Unknown llm spec '{spec}' (anthropic:<model> | openai:<model> | mock)")
