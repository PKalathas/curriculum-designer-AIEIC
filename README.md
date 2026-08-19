# Curriculum Designer Agent

Microservice in the AIEIC Lab Multi-Agent System. Generates lab materials (spec, quiz, rubric) from instructor-provided learning objectives and optional PDF uploads. Supports instructor approval and feedback-driven regeneration.

## Quick start

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # defaults to memory storage + mock LLM for local integration
python -m uvicorn main:app --host 127.0.0.1 --port 8003 --reload
```

Set `LLM_BACKEND=mock` in `.env` for zero-cost local wiring. For a real,
low-cost API, use an OpenAI-compatible provider:

```bash
LLM_BACKEND=openai_compatible
LLM_API_KEY=<your-provider-key>
LLM_BASE_URL=https://api.deepseek.com
LLM_MODEL=deepseek-v4-flash
```

Leave `LLM_BASE_URL` empty and set `LLM_MODEL=gpt-5-nano` for direct OpenAI.
Set `STORAGE_BACKEND=postgres` and `DATABASE_URL=...` only when you want drafts
to persist in the shared AIEIC database.

## Endpoints

| Method | Path | Description |
|---|---|---|
| GET  | `/health` | Health check |
| POST | `/curriculum/generate` | Generate lab from objectives; preserves any uploaded RAG context |
| POST | `/curriculum/generate-with-material` | One-shot form + optional PDF/TXT/MD upload → generate spec, quiz, rubric |
| GET  | `/curriculum/{lab_id}` | Fetch current `LabMaterial` |
| POST | `/curriculum/{lab_id}/upload-material` | Upload one or more PDFs → extract text as generation context |
| POST | `/curriculum/{lab_id}/upload-instructions` | Store instructor instructions as generation context |
| POST | `/curriculum/{lab_id}/approve` | Mark lab approved |
| POST | `/curriculum/{lab_id}/request-changes` | Inject feedback → regenerate quiz + rubric |
| POST | `/curriculum/{lab_id}/check-typos` | LLM proofread across spec, quiz, rubric |
| GET  | `/curriculum/{lab_id}/export/lab.pdf` | Download lab spec and metadata as PDF |
| GET  | `/curriculum/{lab_id}/export/quiz.pdf` | Download quiz as PDF |
| GET  | `/curriculum/{lab_id}/export/rubric.pdf` | Download rubric as PDF |

## Architecture

```
main.py                  App entry point; lifespan inits store + llm_client + graph
config.py                pydantic-settings (reads from .env)
models/curriculum.py     LabMaterial, QuizQuestion, Rubric, upload/response models
routers/curriculum.py    All endpoints
services/
  database.py            SQLAlchemy tables for the shared Postgres runtime
  storage.py             PostgresCurriculumStore + MemoryStore for tests
  llm.py                 Azure / OpenAI-compatible / Mock LLM clients
  prompts.py             Prompt builders for 5 LLM tasks (return system, user tuples)
graphs/generation.py     LangGraph pipeline: spec → quiz → rubric → self_review
tests/                   Stage D (not yet implemented)
doc/
  plan.md                Design decisions and stage breakdown
  handoff.md             Session handoff — current status and where to look for what
  errors-log.md          Known pitfalls and fixes
```

**Generation flow:** `spec_generator → quiz_generator → rubric_generator → self_review`. Self-review issues trigger one retry back to `quiz_generator`. On `request-changes`, spec is preserved and only quiz+rubric are regenerated.

**RAG:** PDF text is extracted with `pypdf` and stored as `material_content` on the `LabMaterial` record. On generation, both `material_content` and `agent_instructions` are injected verbatim into every LLM prompt. No vector store.

## Deployment

```bash
docker build -t curriculum-designer .
docker run --env-file .env -p 8003:8003 curriculum-designer
```

Target: Azure Container Apps.
