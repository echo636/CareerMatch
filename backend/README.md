# CareerMatch Backend

Flask backend scaffold for resume parsing, job ingestion, matching, and gap analysis.

## Persistent app state

Structured resumes and jobs are persisted in **PostgreSQL** (JSONB).
Embedding vectors are stored in **Qdrant** (cosine similarity, auto-created collections).

Infrastructure (default via `docker compose up -d`):

- PostgreSQL 16: `postgresql://careermatch:careermatch@localhost:5432/careermatch`
- Qdrant v1.13.2: `http://localhost:6333`

Configuration:

```env
POSTGRES_DSN=postgresql://careermatch:careermatch@localhost:5432/careermatch
QDRANT_URL=http://localhost:6333
```

Behavior:

- `/api/resumes/upload` parses the resume, computes its embedding once, then stores the structured resume in PostgreSQL and the vector in Qdrant.
- `python import_jobs_offline.py` imports raw job data in the background, computes embeddings, and writes structured jobs to PostgreSQL and vectors to Qdrant.
- Later requests reuse the stored vectors as long as the derived vector payload for that item has not changed.
- If the resume or job content changes, the backend recomputes the embedding and updates the stored cache.
- On startup, default seed jobs are only imported when the persistent job store is empty.

Offline import example:

```bash
python import_jobs_offline.py --input data/jobs.json --batch-size 50 --replace-jobs
```

## Job seed data

By default the backend loads `data/sample_jobs.json` on startup.

To seed the app from the PageFlux SQL dump instead, set:

```env
JOB_DATA_PATH=data/pageflux_dev_jobs_2026-03-23_172811.sql
JOB_DATA_LIMIT=300
```

`JOB_DATA_LIMIT` is optional, but keeping it set while testing makes startup and result inspection easier.

The offline import script can already read the SQL dump directly:

```bash
python import_jobs_offline.py --input data/pageflux_dev_jobs_2026-03-23_172811.sql --limit 300 --batch-size 50
```

Notes:

- The backend now expects `LLM_PROVIDER=qwen` and `EMBEDDING_PROVIDER=qwen`.
- The PageFlux dump is suitable for realistic matching tests because structured fields can be re-extracted from the full JD text through the real Qwen pipeline.
