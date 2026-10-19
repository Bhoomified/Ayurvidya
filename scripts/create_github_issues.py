"""Create the 34 project tasks (handbook Part H) as GitHub issues, with labels.

Needs the GitHub CLI, logged in:   gh auth login
Run from the repository folder:     python scripts/create_github_issues.py
Preview without creating anything:  python scripts/create_github_issues.py --dry-run

Safe to re-run: tasks whose issue title already exists are skipped.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# (id, phase, owner, title, stored-where/code, done-when)
TASKS = [
    ("B1", 1, "bhoomi", "Set up data folders and a cloud backup for raw scans and typed sources", "data/, cloud folder", "Folders match handbook F2; backup syncs"),
    ("B2", 1, "bhoomi", "Type Dalhana's commentary on Su. Ni. 1 in the '# shloka:' format", "data/sources/dalhana_su_ni_1.txt", "All 91 verses covered, proofread once"),
    ("B3", 1, "bhoomi", "Build Amarakosha and Dhatupatha entry files for every word and root of the chapter", "data/sources/*.jsonl", "One line per headword or root"),
    ("B4", 1, "bhoomi", "Collect parallel passages: Charaka Ci. 28 & 29, Ashtanga Hridaya Ni. 15 & 16", "data/sources/crosstext_*.txt", "Files load without errors"),
    ("B5", 1, "bhoomi", "Keep the provenance log: edition, URL, permission for every source file", "data/sources/SOURCES.csv", "No file without a row"),
    ("B6", 1, "bhoomi", "Run build_kb.py; check chunk counts per type; spot-check 20 chunks", "data/kb/", "Counts recorded; no broken Devanagari"),
    ("B7", 2, "bhoomi", "Rebuild the KB index with the chosen embedder; archive every manifest.json", "data/kb/, build log", "Index loads; manifest archived"),
    ("B8", 2, "bhoomi", "Own the cache database: check schema, daily backup copy, documented restore", "data/ayurvidya.sqlite3 + backups", "A restore from backup works"),
    ("B9", 2, "bhoomi", "Write and store 100+ labelled retrieval queries with a scholar (half English, half Sanskrit)", "data/eval/retrieval_qrels.jsonl", "Each query has a confirmed answer"),
    ("B10", 3, "bhoomi", "Export generated steps to Excel for scholars; version every sheet sent out", "outputs/review_v*.xlsx", "Every sheet sent is traceable"),
    ("B11", 3, "bhoomi", "Store CVI ratings; record approvals and corrections in the database", "data/eval/cvi_ratings.csv, shloka_steps", "Every rated item has a status"),
    ("B12", 3, "bhoomi", "Extend storage to verses 31-91: sources indexed, DB rows present, backups current", "data/kb/, DB", "All 90 units have 7 step rows"),
    ("B13", 4, "bhoomi", "Move the cache from SQLite to PostgreSQL on the server", "hosted Postgres, store.py", "API reads from Postgres; tests pass"),
    ("B14", 4, "bhoomi", "Store study data: anonymised IDs, pre/post scores, SUS/MARS, consent forms, restricted access", "data/study/ (not in Git)", "No names in any analysis file"),
    ("B15", 4, "bhoomi", "Freeze and archive the final dataset version for the paper", "tagged release + archive", "Version cited in the paper"),
    ("V1", 1, "vaishnavi", "Set up Python, Git and the virtual environment on both laptops; run the tests", "repo", "Tests pass on both machines and on GitHub Actions"),
    ("V2", 1, "vaishnavi", "Trace one verse through the pipeline in the debugger; explain format_context()", "pipeline.py", "Can explain every step's context"),
    ("V3", 1, "vaishnavi", "Connect a real LLM (Claude key or local Ollama) and run verse 3", "llm.py", "7 valid steps for verse 3"),
    ("V4", 2, "vaishnavi", "Retrieval ablation: 3 embedders x sparse/dense/hybrid on the query set", "scripts/eval_retrieval.py", "Results table filled"),
    ("V5", 2, "vaishnavi", "Choose the embedder (and test the reranker); hand the setting over for B7", "config/settings.yaml", "Choice justified by the table"),
    ("V6", 2, "vaishnavi", "Start the FastAPI server and test every endpoint at /docs", "api.py", "All routes return correct data"),
    ("V7", 2, "vaishnavi", "Demo the chatbot in the terminal on 10 questions", "chatbot.py", "Answers cite sources"),
    ("V8", 3, "vaishnavi", "Run the 7 steps for verses 1-30 and compare with the validated table", "run_pipeline.py", "Validator pass rate recorded"),
    ("V9", 3, "vaishnavi", "Tune prompts and validators using per-step I-CVI", "prompts/, steps.py", "Weak steps improved and re-rated"),
    ("V10", 3, "vaishnavi", "Run verses 31-91", "run_pipeline.py", "All verses generated"),
    ("V11", 3, "vaishnavi", "Evaluate the chatbot: faithfulness, relevance, grounded rate, 10 refusal tests", "evaluation/rag_judge.py", "Metrics table filled"),
    ("V12", 4, "vaishnavi", "Build the Android app: shloka list, shloka with 7 tabs, chat button", "android/ (Kotlin + Compose)", "App works against the local API"),
    ("V13", 4, "vaishnavi", "Deploy the API with the Postgres database and connect the app", "server", "Students can install and use it"),
    ("V14", 4, "vaishnavi", "Analyse study data: paired t-test or Wilcoxon, Hake's gain, SUS, MARS", "evaluation/stats.py", "Results tables and p-values"),
    ("V15", 4, "vaishnavi", "Produce the results tables and figures for the paper", "notebook", "All Part G tables complete"),
    ("S1", 1, "shared", "Learn handbook Part A together; explain each concept to each other", "-", "Both can explain RAG end to end"),
    ("S2", 2, "shared", "Recruit the 6+ scholar panel and get ethics approval", "-", "Panel confirmed; approval letter"),
    ("S3", 3, "shared", "Run scholar review sessions; weekly code review of each other's changes", "-", "All review rounds done"),
    ("S4", 4, "shared", "Run the student study sessions; write the paper", "-", "Paper draft complete"),
]

LABELS = {
    "bhoomi": ("1D76DB", "Bhoomi - storage and data"),
    "vaishnavi": ("D93F0B", "Vaishnavi - AI, app and analysis"),
    "shared": ("5319E7", "Both partners"),
    "phase-1": ("C2E0C6", "Knowledge base, weeks 1-3"),
    "phase-2": ("BFD4F2", "Retrieval + API, weeks 4-5"),
    "phase-3": ("FEF2C0", "Pipeline + CVI, weeks 6-9"),
    "phase-4": ("F9D0C4", "App + study, weeks 10-16"),
    "task": ("EDEDED", "Project task from the handbook"),
}


def gh(*args: str) -> str:
    return subprocess.run(["gh", *args], check=True, capture_output=True, text=True, encoding="utf-8").stdout


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    if args.dry_run:
        for t in TASKS:
            print(f"[{t[0]}] {t[3]}  labels: task, {t[2]}, phase-{t[1]}")
        print(f"{len(TASKS)} issues would be created")
        return
    if not shutil.which("gh"):
        sys.exit("GitHub CLI not found. Install it from https://cli.github.com and run: gh auth login")
    for name, (color, desc) in LABELS.items():
        gh("label", "create", name, "--color", color, "--description", desc, "--force")
    existing = {i["title"] for i in json.loads(gh("issue", "list", "--state", "all", "--limit", "500", "--json", "title"))}
    made = 0
    for tid, phase, owner, title, where, done in TASKS:
        full = f"[{tid}] {title}"
        if full in existing:
            print("exists:", full)
            continue
        body = (f"**Task ID:** {tid}\n**Phase:** {phase}\n**Owner:** {owner}\n\n"
                f"**Stored where / code:** {where}\n**Done when:** {done}\n\n"
                f"Details: handbook Part H (H1 Bhoomi, H2 Vaishnavi, H3 shared).")
        gh("issue", "create", "--title", full, "--body", body, "--label", f"task,{owner},phase-{phase}")
        made += 1
        print("created:", full)
    print(f"done: {made} new issues")


if __name__ == "__main__":
    main()
