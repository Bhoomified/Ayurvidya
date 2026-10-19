"""Check that the AI model (LLM) in your settings / .env is reachable and answers.

    python scripts/check_llm.py
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from ayurvidya.config import load_settings  # noqa: E402
from ayurvidya.llm import LLMError, make_llm  # noqa: E402


def main() -> None:
    s = load_settings()
    print(f"LLM setting : {s.llm}")
    if s.llm_base_url:
        print(f"Server URL  : {s.llm_base_url}")
    if s.llm == "mock":
        print("\nYou are still on the MOCK model (dummy answers).")
        print("Set AYV_LLM in your .env file, e.g.  AYV_LLM=anthropic:claude-sonnet-5-5")
        return
    try:
        llm = make_llm(s.llm, s.llm_base_url, s.temperature, 200)
        t0 = time.time()
        reply = llm.complete("You are a Sanskrit teacher. Answer in one short English sentence.",
                             "What does the word वायुः mean?")
    except LLMError as e:
        print(f"\nFAILED: {e}")
        print("Check: the API key in .env, internet connection, the model name, "
              "and for Ollama that 'ollama serve' is running.")
        sys.exit(1)
    print(f"\nReply ({time.time() - t0:.1f} s): {reply}")
    print("\nOK - the model is connected.")


if __name__ == "__main__":
    main()