"""Cache database: the three tables from the project design (chapters, shlokas, shloka_steps).

SQLite (built into Python) is used for development and the study; the SQL is plain ANSI so the same
schema runs on PostgreSQL for deployment. The 7 steps are run OFFLINE once per shloka and stored here;
the app only reads, so students get answers instantly and the LLM bill is paid once.
"""
from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path

from .schema import Shloka, StepResult

SCHEMA = """
CREATE TABLE IF NOT EXISTS chapters (
    id        TEXT PRIMARY KEY,          -- 'su.ni.1'
    samhita   TEXT NOT NULL,
    sthana    TEXT NOT NULL,
    number    INTEGER NOT NULL,
    name      TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS shlokas (
    id         TEXT PRIMARY KEY,         -- 'su.ni.1.3'
    chapter_id TEXT NOT NULL REFERENCES chapters(id),
    number     TEXT NOT NULL,
    ord        INTEGER NOT NULL,
    text       TEXT NOT NULL,
    variant    TEXT NOT NULL DEFAULT '',
    is_prose   INTEGER NOT NULL DEFAULT 0,
    topic      TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS shloka_steps (
    shloka_id      TEXT NOT NULL REFERENCES shlokas(id),
    step_number    INTEGER NOT NULL CHECK (step_number BETWEEN 1 AND 7),
    output         TEXT NOT NULL,
    valid          INTEGER NOT NULL,
    issues         TEXT NOT NULL DEFAULT '[]',
    retrieved_ids  TEXT NOT NULL DEFAULT '[]',
    model          TEXT NOT NULL,
    prompt_version TEXT NOT NULL,
    status         TEXT NOT NULL DEFAULT 'generated',   -- generated | reviewed | approved
    reviewer_note  TEXT NOT NULL DEFAULT '',
    created_at     REAL NOT NULL,
    PRIMARY KEY (shloka_id, step_number)
);
CREATE INDEX IF NOT EXISTS ix_shlokas_chapter ON shlokas(chapter_id, ord);
"""


class Store:
    def __init__(self, path: str | Path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(str(path), check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA foreign_keys = ON")
        self.db.executescript(SCHEMA)

    def close(self) -> None:
        self.db.close()

    # writes ----------------------------------------------------------
    def upsert_chapter(self, cid: str, samhita: str, sthana: str, number: int, name: str) -> None:
        with self.db:
            self.db.execute("INSERT INTO chapters VALUES (?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET name=excluded.name",
                            (cid, samhita, sthana, number, name))

    def upsert_shlokas(self, chapter_id: str, shlokas: list[Shloka]) -> None:
        with self.db:
            for i, s in enumerate(shlokas):
                self.db.execute(
                    "INSERT INTO shlokas VALUES (?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET "
                    "text=excluded.text, variant=excluded.variant, topic=excluded.topic, ord=excluded.ord",
                    (s.id, chapter_id, s.number, i, s.text, s.variant, int(s.is_prose), s.topic))

    def save_step(self, r: StepResult) -> None:
        with self.db:
            self.db.execute(
                "INSERT INTO shloka_steps (shloka_id, step_number, output, valid, issues, retrieved_ids, model, "
                "prompt_version, status, created_at) VALUES (?,?,?,?,?,?,?,?, 'generated', ?) "
                "ON CONFLICT(shloka_id, step_number) DO UPDATE SET output=excluded.output, valid=excluded.valid, "
                "issues=excluded.issues, retrieved_ids=excluded.retrieved_ids, model=excluded.model, "
                "prompt_version=excluded.prompt_version, status='generated', created_at=excluded.created_at",
                (r.shloka_id, r.step, r.output, int(r.valid), json.dumps(r.issues, ensure_ascii=False),
                 json.dumps(r.retrieved_ids), r.model, r.prompt_version, time.time()))

    def set_review(self, shloka_id: str, step: int, status: str, note: str = "", output: str | None = None) -> None:
        if status not in ("generated", "reviewed", "approved"):
            raise ValueError("status must be generated | reviewed | approved")
        with self.db:
            if output is not None:
                self.db.execute("UPDATE shloka_steps SET output=?, status=?, reviewer_note=? "
                                "WHERE shloka_id=? AND step_number=?", (output, status, note, shloka_id, step))
            else:
                self.db.execute("UPDATE shloka_steps SET status=?, reviewer_note=? WHERE shloka_id=? AND step_number=?",
                                (status, note, shloka_id, step))

    # reads -----------------------------------------------------------
    def chapters(self) -> list[dict]:
        return [dict(r) for r in self.db.execute("SELECT * FROM chapters ORDER BY samhita, sthana, number")]

    def shlokas(self, chapter_id: str) -> list[dict]:
        return [dict(r) for r in self.db.execute(
            "SELECT id, number, text, topic FROM shlokas WHERE chapter_id=? ORDER BY ord", (chapter_id,))]

    def shloka(self, shloka_id: str) -> dict | None:
        r = self.db.execute("SELECT * FROM shlokas WHERE id=?", (shloka_id,)).fetchone()
        return dict(r) if r else None

    def steps(self, shloka_id: str) -> dict[int, dict]:
        out = {}
        for r in self.db.execute("SELECT * FROM shloka_steps WHERE shloka_id=? ORDER BY step_number", (shloka_id,)):
            d = dict(r)
            d["issues"] = json.loads(d["issues"])
            d["retrieved_ids"] = json.loads(d["retrieved_ids"])
            out[d["step_number"]] = d
        return out

    def cached(self, shloka_id: str, step: int, prompt_version: str, model: str) -> dict | None:
        """A cached output is reused only if prompt AND model are unchanged — or a scholar approved it."""
        r = self.db.execute("SELECT * FROM shloka_steps WHERE shloka_id=? AND step_number=?", (shloka_id, step)).fetchone()
        if not r:
            return None
        if r["status"] == "approved" or (r["prompt_version"] == prompt_version and r["model"] == model and r["valid"]):
            return dict(r)
        return None
