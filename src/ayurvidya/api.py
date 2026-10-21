"""HTTP API for the Android app (FastAPI).

    GET  /chapters                         list chapters
    GET  /chapters/{chapter_id}/shlokas    list shlokas of a chapter
    GET  /shlokas/{shloka_id}              shloka + its 7 cached step outputs (instant, no LLM call)
    POST /chat                             {question, shloka_id?, history?} -> grounded answer + citations
    POST /admin/shlokas/{shloka_id}/run    (re)generate the 7 steps for one shloka   [needs ADMIN_TOKEN]
    PUT  /admin/shlokas/{id}/steps/{n}     scholar review: approve or correct a step  [needs ADMIN_TOKEN]
    GET  /app/                             the mobile web app (files in web/)

Run:  python scripts/serve.py                 (prints the address to open on your phone)
"""
from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .llm import LLMError
from .schema import Shloka
from .service import build_app
from .sources import source_label

WEB_DIR = Path(__file__).resolve().parents[2] / "web"

app_state = build_app()
chunks_by_id = {c.id: c for c in app_state.kb.chunks}
api = FastAPI(title="Ayurvidya RAG", version="1.1")


class ChatIn(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    shloka_id: str | None = None
    history: list[tuple[str, str]] = []


class ReviewIn(BaseModel):
    status: str = Field(pattern="^(generated|reviewed|approved)$")
    note: str = ""
    output: str | None = None


def _admin(token: str | None) -> None:
    expected = os.environ.get("ADMIN_TOKEN")
    if not expected or token != expected:
        raise HTTPException(401, "admin token required")


@api.get("/chapters")
def chapters():
    return app_state.store.chapters()


@api.get("/chapters/{chapter_id}/shlokas")
def shlokas(chapter_id: str):
    return app_state.store.shlokas(chapter_id)


@api.get("/shlokas/{shloka_id}")
def shloka(shloka_id: str):
    sh = app_state.store.shloka(shloka_id)
    if not sh:
        raise HTTPException(404, "shloka not found")
    steps = app_state.store.steps(shloka_id)
    return {"shloka": sh, "steps": {n: {"output": d["output"], "status": d["status"], "valid": bool(d["valid"])}
                                    for n, d in steps.items()}}


@api.post("/chat")
def chat(body: ChatIn):
    try:
        a = app_state.chatbot.ask(body.question, body.shloka_id, body.history)
    except KeyError as e:
        raise HTTPException(404, str(e))
    except LLMError:
        raise HTTPException(503, "The AI is busy or today's free limit is used up. Please try again later.")
    return {"answer": a.answer, "citations": a.citations, "grounded": a.grounded,
            "sources": [{"id": c, "label": source_label(c, chunks_by_id)} for c in a.citations]}


@api.post("/admin/shlokas/{shloka_id}/run")
def run(shloka_id: str, force: bool = False, x_admin_token: str | None = Header(default=None)):
    _admin(x_admin_token)
    row = app_state.store.shloka(shloka_id)
    if not row:
        raise HTTPException(404, "shloka not found")
    sh = Shloka(id=row["id"], samhita="sushruta", sthana="nidana", chapter=int(row["chapter_id"].split(".")[-1]),
                number=row["number"], text=row["text"], is_prose=bool(row["is_prose"]), variant=row["variant"])
    res = app_state.orchestrator.run_shloka(sh, force=force)
    return {n: {"valid": r.valid, "issues": r.issues, "attempts": r.attempts} for n, r in res.items()}


@api.put("/admin/shlokas/{shloka_id}/steps/{step}")
def review(shloka_id: str, step: int, body: ReviewIn, x_admin_token: str | None = Header(default=None)):
    _admin(x_admin_token)
    app_state.store.set_review(shloka_id, step, body.status, body.note, body.output)
    return {"ok": True}


# ---------------------------------------------------------------- mobile web app
@api.get("/", include_in_schema=False)
def home():
    return RedirectResponse("/app/")


if WEB_DIR.exists():
    api.mount("/app", StaticFiles(directory=WEB_DIR, html=True), name="app")