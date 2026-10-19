"""Try the chatbot in the terminal.

    python scripts/chat_cli.py --shloka su.ni.1.13
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")   # Devanagari on Windows consoles

from ayurvidya.service import build_app  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--shloka", default=None)
    args = ap.parse_args()
    app = build_app()
    history: list[tuple[str, str]] = []
    print("Ask a question (empty line to quit).")
    while True:
        q = input("\nYou: ").strip()
        if not q:
            break
        a = app.chatbot.ask(q, args.shloka, history)
        print(f"\nTutor: {a.answer}\n  sources: {', '.join(a.citations) or '—'}  grounded: {a.grounded}")
        history.append((q, a.answer))


if __name__ == "__main__":
    main()
