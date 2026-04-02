# Qwen Integration

The backend now uses real Qwen services for both structured extraction and embeddings.

## What changed

- `LLM_PROVIDER` must be `qwen`.
- `EMBEDDING_PROVIDER` must be `qwen`.
- Startup seed jobs are also imported through the real Qwen job normalization path.
- If a Qwen request fails, the API returns an explicit error instead of silently fabricating a local fallback result.

## Required configuration

Copy `backend/.env.example` to `backend/.env`, then set:

```env
LLM_PROVIDER=qwen
EMBEDDING_PROVIDER=qwen
DASHSCOPE_API_KEY=your_dashscope_api_key
QWEN_LLM_MODEL=qwen-plus-latest
QWEN_EMBEDDING_MODEL=text-embedding-v4
QWEN_EMBEDDING_DIMENSIONS=1024
```

## Recommended validation

1. Start the backend.
2. Verify `GET /api/health` returns the expected Qwen models.
3. Upload a real resume and confirm the response still contains `basicInfo`, `skills`, `projects`, and `expectedSalary`.
4. Re-import jobs with `python backend/scripts/import_jobs_offline.py ...` so persisted job vectors are rebuilt with the real embedding model.
5. Run `backend/test/test_job_normalization_compare.py` to compare raw job JSON with processed JSON and confirm the real APIs return stable output.

## Notes

- The Qwen client uses DashScope's OpenAI-compatible endpoint.
- Structured extraction still goes through local normalization after the model response, so downstream services keep the same JSON shape.
- If you change the embedding model or dimensions, rebuild the persistent vectors from fresh source data.
