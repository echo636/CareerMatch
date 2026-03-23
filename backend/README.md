# CareerMatch Backend

Flask backend scaffold for resume parsing, job ingestion, matching, and gap analysis.

## Job seed data

By default the backend loads `data/sample_jobs.json` on startup.

To seed the app from the PageFlux SQL dump instead, set:

```env
JOB_DATA_PATH=data/pageflux_dev_jobs_2026-03-23_172811.sql
JOB_DATA_LIMIT=300
```

`JOB_DATA_LIMIT` is optional, but keeping it set while testing makes startup and result inspection easier.

You can also convert the dump into the JSON format expected by `/api/jobs/import`:

```bash
python convert_job_seed.py --input data/pageflux_dev_jobs_2026-03-23_172811.sql --output data/pageflux_dev_jobs.json --limit 300
```

Notes:

- With `LLM_PROVIDER=mock`, the dump can be used for smoke tests and basic matching tests, but skill extraction is heuristic.
- With `LLM_PROVIDER=qwen`, the same data is more suitable for realistic matching tests because structured fields can be re-extracted from the full JD text.
