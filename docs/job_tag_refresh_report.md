# Job Tag Refresh Report

## Background

The previous job-tag flow had two practical issues:

1. `tags` generation in job normalization was too weak.
It only trusted existing tags, and only used a minimal fallback when tags were empty.

2. Existing Postgres jobs had no low-risk refresh path.
The `jobs.payload` JSON could be updated, but there was no dedicated script to rebuild tags and refresh vectors in a controlled way.

This created noisy tag sets such as:

- tech tags falling into `general`
- missing `project / education / language` tags even when the structured payload already contained enough evidence
- historical Postgres data drifting away from the current normalization rules

## Changes

### 1. Enriched job context for standardized payloads

File:

- `backend/app/job_enrichment.py`

`build_job_context_text()` now includes more structured content when the source payload is already normalized:

- responsibilities
- highlights
- required / optional / bonus skill names and descriptions
- core / bonus experience names, descriptions, and keywords
- majors, certifications, and languages from education constraints
- existing tag names

This matters for historical Postgres jobs because they no longer rely on raw source fields like `job_keys` or `skill_tags` to recover context.

### 2. Unified tag generation

File:

- `backend/app/job_enrichment.py`

Added `infer_job_tags()` as the shared tag builder.

It now builds a more balanced tag set from:

- normalized skills -> `tech`
- inferred topics / experience items -> `project`
- raw `job_keys` style business labels -> `domain`
- `company_industry` -> `industry`
- majors / certifications -> `education`
- language requirements -> `language`
- short meaningful highlights -> `general`

It also:

- deduplicates tags
- fixes obvious category mistakes such as skill-like tags stored as `general`
- limits each category so tags stay compact

### 3. Job normalization now always rebuilds tags

File:

- `backend/app/clients/llm.py`

`QwenLLMClient._normalize_job()` no longer uses the old "only backfill tags when empty" behavior.
It now always rebuilds tags from the final normalized structure, which means:

- new imports get better tags
- standardized payloads can be re-normalized locally without another LLM round-trip
- historical Postgres jobs can be refreshed with the same rule set

### 4. Existing Postgres jobs can now be refreshed in batch

File:

- `backend/scripts/rebuild_job_tags_postgres.py`

The new script:

- loads jobs from Postgres
- re-normalizes them through the local fast path
- compares old vs new tags / role categories / vector payload
- saves changed job payloads back to Postgres
- optionally refreshes Qdrant vectors
- writes a managed report under `backend/test/reports/job_tag_refresh/`

## How To Update Existing Postgres Data

Dry run first:

```powershell
python backend\scripts\rebuild_job_tags_postgres.py --dry-run
```

Refresh payloads only:

```powershell
python backend\scripts\rebuild_job_tags_postgres.py --skip-vectors
```

Refresh payloads and vectors:

```powershell
python backend\scripts\rebuild_job_tags_postgres.py
```

Refresh only specific jobs:

```powershell
python backend\scripts\rebuild_job_tags_postgres.py --job-id <job_id_1> --job-id <job_id_2>
```

Limit to a sample batch:

```powershell
python backend\scripts\rebuild_job_tags_postgres.py --dry-run --limit 50
```

Notes:

- Without `--skip-vectors`, the script requires `DASHSCOPE_API_KEY` because vector payload changes need fresh embeddings.
- With `--skip-vectors`, only Postgres payloads are updated; Qdrant vectors remain unchanged.
- For full consistency, run without `--skip-vectors`.

## Verification

Passed:

```text
python -m py_compile backend\app\job_enrichment.py backend\app\clients\llm.py backend\scripts\rebuild_job_tags_postgres.py backend\test\test_job_tag_enrichment.py
python -m unittest backend.test.test_job_tag_enrichment backend.test.test_matching_filters
python backend\scripts\rebuild_job_tags_postgres.py --help
```

Coverage added:

- structured payload context can be reconstructed from normalized jobs
- tag generation builds `tech / project / domain / industry / education / language / general`
- standardized job payload re-normalization upgrades old sparse tags
- previous `direction_mismatch` regression tests still pass

## Current Limitation

The script was not executed against the live local Postgres instance in this change set because the local database connection was unavailable during implementation.
The code path and report output are ready; the actual refresh should be run once Postgres and Qdrant are available.
