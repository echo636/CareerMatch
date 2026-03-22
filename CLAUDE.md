# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

CareerMatch is an AI-driven resume-to-job matching platform. It processes resumes and job descriptions into structured data, performs multi-stage matching (vector recall → filtering → scoring → ranking), and generates gap analysis reports. The UI is in Chinese.

## Development Commands

### Infrastructure
```bash
docker compose up -d   # PostgreSQL :5432, Qdrant :6333, MinIO :9000
```

### Backend (Flask, Python 3.11+)
```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -e .
cp .env.example .env
python run.py          # http://localhost:5000
```

### Frontend (Next.js 15, React 19, TypeScript)
```bash
cd frontend
npm install
npm run dev            # http://localhost:3000
npm run build          # production build
npm run typecheck      # tsc --noEmit
```

## Architecture

**Layered backend** in `backend/app/`:
- `api/routes/` — Flask Blueprints: `health`, `resumes`, `jobs`, `matches`, `gap`
- `services/` — Business logic: `resume_pipeline`, `job_pipeline`, `matching`, `gap_analysis`
- `clients/` — External adapters: `llm` (mock), `embedding`, `vector_store`, `document_parser`, `object_storage`
- `repositories/in_memory.py` — In-memory data store (prototype for PostgreSQL/Qdrant)
- `domain/models.py` — Dataclass models (`ResumeProfile`, `JobProfile`, `MatchResult`, `GapReport`) with snake_case→camelCase serialization
- `bootstrap.py` — Service container / dependency injection setup
- `__init__.py` — Flask app factory

**Frontend** in `frontend/`:
- Next.js App Router in `app/` — pages: home, `/resume` (upload), `/matches` (results), `/admin/jobs` (import)
- `lib/` — API client utilities
- `types/` — TypeScript type definitions matching backend models

**Data models also defined in Go** at repo root: `job_data.go`, `resume_data.go` — these define the canonical JD and resume schemas.

## Key Design Decisions

- **Mock integrations**: LLM client uses regex/keyword matching, vector store uses SHA256-based pseudo-vectors. All clients are abstracted behind interfaces for future swap to real services (Qdrant, OpenAI/Claude, MinIO).
- **Matching weights**: vector similarity 20%, skills 35%, experience 25%, education 10%, salary 10% (in `services/matching.py`).
- **DI via service container**: All services/clients are wired in `bootstrap.py` — add new dependencies there.
- **JSON serialization**: `domain/models.py` auto-converts snake_case fields to camelCase for API responses.

## API Endpoints

```
GET  /api/health
GET  /api/resumes/demo
GET  /api/resumes/<resume_id>
POST /api/resumes/upload          # multipart file or text body
GET  /api/jobs
POST /api/jobs/import             # JSON array of jobs
POST /api/matches/recommend       # { resumeId, topK }
POST /api/gap/report              # { resumeId, topK }
```
