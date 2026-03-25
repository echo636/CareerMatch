# Resume Flow Testing

This document explains how to use the real-Qwen smoke test script for the resume upload flow, what outputs to inspect, and which backend stages each mode validates.

## Purpose

The script is intended for two checks:

- Verify that DashScope / Qwen can be called successfully with the current environment.
- Verify that the full resume upload pipeline works end to end after a user uploads a resume.

The script file is:

`backend/scripts/test_resume_flow.py`

The sample resume used by default is:

`backend/scripts/sample_resume.txt`

## What the script tests

The script supports three modes:

- `direct`: calls `QwenLLMClient.extract_resume(...)` directly.
- `upload`: calls the local backend API, then continues into matching and gap analysis.
- `both`: runs `direct` first, then `upload`.

## Preconditions

Before running the script, make sure:

1. `backend/.env` contains a valid `DASHSCOPE_API_KEY`.
2. `LLM_PROVIDER=qwen`.
3. `EMBEDDING_PROVIDER=qwen`.
4. The backend process is already running if you want to use `upload` or `both`.
5. `NEXT_PUBLIC_API_BASE_URL` is not required for this script because it talks to the backend directly.

Recommended configuration:

```env
LLM_PROVIDER=qwen
EMBEDDING_PROVIDER=qwen
QWEN_LLM_MODEL=qwen-plus-latest
QWEN_EMBEDDING_MODEL=text-embedding-v4
```

## Commands

Run from the repo root.

Direct LLM only:

```bash
python backend/scripts/test_resume_flow.py --mode direct
```

Full upload flow only:

```bash
python backend/scripts/test_resume_flow.py --mode upload
```

Run both:

```bash
python backend/scripts/test_resume_flow.py --mode both
```

Use a custom backend URL:

```bash
python backend/scripts/test_resume_flow.py --mode upload --api-base-url http://127.0.0.1:5000/api
```

Use a custom resume file:

```bash
python backend/scripts/test_resume_flow.py --mode both --file path/to/your_resume.txt
```

Change the number of recommended jobs requested:

```bash
python backend/scripts/test_resume_flow.py --mode upload --top-k 5
```

## How to read the output

The script prints JSON blocks with titles like:

- `[health]`
- `[direct-llm]`
- `[upload]`
- `[matches]`
- `[gap]`

### 1. `health`

Check:

- `ai.llmProvider`
- `ai.llmModel`
- `ai.embeddingProvider`
- `ai.embeddingModel`

Expected:

- `llmProvider = qwen`
- `embeddingProvider = qwen`

This validates:

- The backend loaded the expected `.env` configuration.
- The running backend instance is the one you think you are testing.

### 2. `direct-llm`

Check:

- `resumeId`
- `name`
- `currentTitle`
- `skillCount`
- `projectCount`
- `summary`

Expected:

- The request returns successfully without timeout or permission errors.
- `name` matches the resume text.
- `currentTitle` is reasonable for the resume content.
- `skillCount` and `projectCount` are greater than `0` for a normal technical resume.
- `summary` reflects the uploaded content, not an unrelated template.

This validates:

- DashScope connectivity works from the current environment.
- `QwenLLMClient` request formatting is valid.
- JSON-mode response parsing works.
- Resume normalization still produces the expected field shape.

### 3. `upload`

Check:

- `resumeId`
- `name`
- `skillCount`
- `projectCount`

Expected:

- The API returns `resumeId`.
- `name` is populated.
- `skillCount` and `projectCount` are non-zero for a valid resume.

This validates:

- Multipart form upload works.
- `POST /api/resumes/upload` works.
- Resume text extraction works for the provided file.
- The backend invokes the real Qwen extraction path.
- The structured resume is serialized correctly and returned to the client.

### 4. `matches`

Check:

- `count`
- `topJob`

Expected:

- `count` is usually greater than `0` if job seed data is loaded and the resume is relevant.
- `topJob` is a real title from the loaded job set.

This validates:

- The uploaded resume was stored and can be referenced by `resumeId`.
- The real embedding path works.
- `POST /api/matches/recommend` works.
- Match ranking completes without runtime errors.

### 5. `gap`

Check:

- `baselineRoles`
- `missingSkills`
- `insightCount`

Expected:

- `baselineRoles` contains job titles used as comparison targets.
- `insightCount` is normally `3`.
- `missingSkills` may be empty if the sample resume already covers many required skills.

This validates:

- `POST /api/gap/report` works.
- Matching output can be consumed by gap analysis.
- Gap insight generation calls the real Qwen path and returns structured output.

## Typical healthy result

A healthy run usually looks like this:

- `health.ai.llmProvider = qwen`
- `health.ai.embeddingProvider = qwen`
- `upload.skillCount > 0`
- `upload.projectCount > 0`
- `matches.count > 0`
- `gap.insightCount = 3`

## Failure patterns

### Qwen timeout

Symptoms:

- API returns an error like `Qwen chat request timed out after ... seconds.`

Recommended checks:

- Increase `DASHSCOPE_TIMEOUT_SEC`.
- Retry with a shorter resume.
- Check whether the current model is overloaded or rate-limited.

### Network / permission error in `direct`

Symptoms:

- Errors such as socket permission issues or `URLError`.

Recommended checks:

- Confirm whether the machine, proxy, firewall, or sandbox policy allows outbound HTTPS requests.
- Compare `direct` mode and `upload` mode results to isolate environment differences.

### Upload succeeds but `matches.count = 0`

Meaning:

- Resume extraction succeeded, but no seeded jobs passed recall or filtering.

Recommended checks:

- Confirm startup seed data loaded correctly.
- Re-import jobs using the real Qwen import path if needed.
- Try a resume that is closer to the seeded job set.

## Suggested test order

1. Run `direct` first to confirm Qwen is reachable.
2. Run `upload` to confirm backend flow is healthy.
3. Open the frontend and manually upload a real resume.
4. If frontend behavior differs from the script result, debug the frontend separately.
