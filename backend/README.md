# CareerMatch Backend

Flask backend scaffold for resume parsing, job ingestion, matching, and gap analysis.

## Persistent app state

Structured resumes, structured jobs, and cached embeddings are persisted in SQLite.
By default the backend writes them to `data/app_state.sqlite3`.
You can override that location with:

```env
APP_STATE_DB_PATH=data/app_state.sqlite3
```

Behavior:

- `/api/resumes/upload` parses the resume, computes its embedding once, then stores both the structured resume and vector cache.
- `python import_jobs_offline.py` imports raw job data in the background, computes embeddings, and writes the structured jobs plus vector cache into SQLite.
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

You can also convert the dump into the JSON format consumed by the offline import script:

```bash
python convert_job_seed.py --input data/pageflux_dev_jobs_2026-03-23_172811.sql --output data/pageflux_dev_jobs.json --limit 300
```

Notes:

- The backend now expects `LLM_PROVIDER=qwen` and `EMBEDDING_PROVIDER=qwen`.
- The PageFlux dump is suitable for realistic matching tests because structured fields can be re-extracted from the full JD text through the real Qwen pipeline.
