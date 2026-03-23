# Qwen Integration

The backend now supports switching from mock AI to real Qwen services without changing the API contract used by the frontend.

## What changed

- `LLM_PROVIDER` controls whether resume extraction, job structuring, and gap insights use `mock` or `qwen`.
- `EMBEDDING_PROVIDER` controls whether vectorization uses the local hash embedding or Qwen embeddings.
- Demo seed data still uses the mock extractor to avoid paying for LLM calls on every backend startup.
- If a Qwen request fails, the API returns `502` instead of silently corrupting the response shape.

## Recommended rollout

1. Start with `LLM_PROVIDER=qwen` and `EMBEDDING_PROVIDER=mock`.
2. Verify `POST /api/resumes/upload`, `POST /api/jobs/import`, and `POST /api/gap/report`.
3. After the structured output quality is acceptable, switch `EMBEDDING_PROVIDER=qwen`.
4. Re-import jobs and re-upload resumes so all stored vectors share the same embedding model.

## Environment variables

Copy `backend/.env.example` to `backend/.env`, then set:

```env
LLM_PROVIDER=qwen
EMBEDDING_PROVIDER=qwen
DASHSCOPE_API_KEY=your_dashscope_api_key
QWEN_LLM_MODEL=qwen-plus-latest
QWEN_EMBEDDING_MODEL=text-embedding-v4
QWEN_EMBEDDING_DIMENSIONS=1024
```

You can also keep `EMBEDDING_PROVIDER=mock` during the first phase to reduce cost while validating extraction quality.

## Smoke test

After starting the backend, verify:

- `GET /api/health` returns the selected providers and models.
- Upload a real resume and confirm the response still contains `basicInfo`, `skills`, `projects`, and `expectedSalary`.
- Import a raw JD payload and confirm `skillRequirements`, `experienceRequirements`, and `educationConstraints` are filled.

## Notes

- The Qwen client uses DashScope's OpenAI-compatible endpoint.
- Structured extraction uses JSON-mode output plus local normalization, so downstream services keep the same shape even when the model omits optional fields.
- If you change the embedding model or dimensions, rebuild the in-memory or vector index from fresh source data.
