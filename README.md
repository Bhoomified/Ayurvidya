# Ayurvidya RAG

Retrieval-augmented system that teaches **Sushruta Samhita, Nidana Sthana, Chapter 1 (Vatavyadhi Nidana)**
through the 7 Ayurvidya steps — Sampradanam, Padavibhaga, Anvaya, Anvayartha, Bhavartha, Padakrityam,
Dhvanitartha — plus a grounded doubt-clearing chatbot. Research project of Bhoomi and Vaishnavi.

The full explanation (concepts from zero, architecture, evaluation, work plan) is in the project handbook.

## Quick start (Windows / macOS / Linux, Python 3.10+)

```bash
.\setup.ps1          # Windows PowerShell   (macOS/Linux: bash setup.sh)
.\.venv\Scripts\Activate.ps1                # activate the environment
python -m unittest discover -s tests -v      # 26 tests, fully offline (TF-IDF + mock LLM)
pip install -r requirements.txt               # later, for the API and real embedding models

python scripts/build_kb.py                   # builds data/kb + the SQLite cache
python scripts/run_pipeline.py --range 1 5 --export outputs/demo.xlsx    # mock LLM: wiring check
```

Real run (multilingual embeddings + Claude):

```bash
cp .env.example .env            # fill ANTHROPIC_API_KEY, ADMIN_TOKEN
set -a; source .env; set +a     # Windows PowerShell: see handbook Part F
AYV_EMBEDDER=st:BAAI/bge-m3 python scripts/build_kb.py
python scripts/eval_retrieval.py                      # retrieval ablation table
python scripts/run_pipeline.py --range 1 30 --export outputs/su_ni_1_generated.xlsx
python scripts/chat_cli.py --shloka su.ni.1.13
PYTHONPATH=src uvicorn ayurvidya.api:api --reload     # API for the Android app
```

Free/local alternative to Claude: install Ollama, `ollama pull qwen2.5:14b`, then
`AYV_LLM=openai:qwen2.5:14b AYV_LLM_BASE_URL=http://localhost:11434/v1`.

## Working on GitHub

- `main` is protected: every change goes through a pull request that the other partner approves.
- Branch names: `b/<task-id>-short-name` (Bhoomi), `v/<task-id>-short-name` (Vaishnavi), e.g. `v/V3-real-llm`.
- GitHub Actions runs the tests on every push (`.github/workflows/tests.yml`).
- `python scripts/create_github_issues.py` creates the 34 tasks of handbook Part H as issues.

## Layout

```
config/settings.yaml        all tunable settings (override with AYV_<KEY> env vars)
prompts/                    the 7 step prompts (verbatim from the project README), grounding rules, chatbot
data/raw/                   NIIMH mula text of Su. Ni. 1 (91 verses)
data/gold/                  validated 7-step table (verses 1-30) -> few-shot examples + evaluation reference
data/sources/               commentary, kosha, dhatu, grammar, parallel texts you add (see its README)
data/eval/                  retrieval_qrels.jsonl (labelled queries), CVI rating sheets
src/ayurvidya/
  text.py        Devanagari normalisation, IAST transliteration, akshara counting, pada splitting
  ingest.py      mula/gold/source loaders, shloka-boundary chunking
  embed.py       TF-IDF (offline) and sentence-transformers embedders
  index.py       exact NumPy vector store (+ optional Chroma), BM25, KnowledgeBase persistence
  retrieve.py    hybrid retrieval: dense + BM25 -> Reciprocal Rank Fusion -> optional reranker
  steps.py       the 7 step specs: retrieval routing, deterministic Sampradanam, output validators
  pipeline.py    orchestrator: sequential steps, context passing, validate-and-retry, caching
  store.py       SQLite cache (chapters, shlokas, shloka_steps) with scholar review status
  chatbot.py     grounded chatbot with citations
  api.py         FastAPI endpoints for the app
  export.py      cached outputs -> Excel in the template layout
  evaluation/    retrieval metrics, CVI + modified kappa, RAGAS-style judge, paired tests, SUS, MARS
scripts/                    build_kb, run_pipeline, eval_retrieval, compute_cvi, chat_cli
tests/test_all.py           unit + end-to-end tests
```
