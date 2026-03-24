# Resume Flow Testing

This document explains how to use the real-LLM smoke test script for the resume upload flow, what outputs to inspect, and which parts of the backend logic each mode validates.

## Purpose

The script is intended for two kinds of checks:

- Verify whether DashScope / Qwen can be called successfully with the current environment.
- Verify whether the full resume upload pipeline works end to end after a user uploads a resume.

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
3. The backend process is already running if you want to use `upload` or `both`.
4. `NEXT_PUBLIC_API_BASE_URL` is not required for this script because it talks to the backend directly.

Recommended first-stage configuration:

```env
LLM_PROVIDER=qwen
EMBEDDING_PROVIDER=mock
QWEN_LLM_MODEL=qwen-plus-latest
```

This keeps real resume extraction and gap insight generation enabled while avoiding embedding cost during early validation.

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

Example fields to inspect:

- `ai.llmProvider`
- `ai.llmModel`
- `ai.embeddingProvider`

What should look correct:

- `llmProvider` should be `qwen` if you are validating the real LLM path.
- `embeddingProvider` should match your current rollout plan, commonly `mock` in phase one.

What this validates:

- The backend loaded the expected `.env` configuration.
- The running backend instance is the one you think you are testing.

### 2. `direct-llm`

Example fields to inspect:

- `resumeId`
- `name`
- `currentTitle`
- `skillCount`
- `projectCount`
- `summary`

What should look correct:

- The request should return successfully without timeout or permission errors.
- `name` should match the resume text.
- `currentTitle` should be reasonable for the resume content.
- `skillCount` and `projectCount` should be greater than `0` for a normal technical resume.
- `summary` should reflect the uploaded content, not an unrelated template.

What this validates:

- DashScope connectivity works from the current environment.
- `QwenLLMClient` request formatting is valid.
- JSON-mode response parsing works.
- Resume normalization still produces the expected field shape after model output is merged.

What this does not validate:

- File upload handling.
- Document parsing.
- Resume persistence.
- Matching and gap analysis APIs.

### 3. `upload`

Example fields to inspect:

- `resumeId`
- `name`
- `skillCount`
- `projectCount`

What should look correct:

- The API should return `resumeId`.
- `name` should be populated.
- `skillCount` and `projectCount` should be non-zero for a valid resume.

What this validates:

- Multipart form upload works.
- `POST /api/resumes/upload` works.
- Resume text extraction path works for the provided file.
- The backend actually invokes the configured LLM extraction path.
- The structured resume is serialized correctly and returned to the client.

### 4. `matches`

Example fields to inspect:

- `count`
- `topJob`

What should look correct:

- `count` should usually be greater than `0` if job seed data is loaded and the resume is relevant.
- `topJob` should be a real title from the loaded job set.

What this validates:

- The uploaded resume was stored and can be referenced by `resumeId`.
- The vectorization path works for the current embedding provider.
- `POST /api/matches/recommend` works.
- Match ranking can complete without runtime errors.

### 5. `gap`

Example fields to inspect:

- `baselineRoles`
- `missingSkills`
- `insightCount`

What should look correct:

- `baselineRoles` should contain job titles used as comparison targets.
- `insightCount` should normally be `3`.
- `missingSkills` may be empty if the sample resume already covers many required skills.

What this validates:

- `POST /api/gap/report` works.
- Matching output can be consumed by gap analysis.
- Gap insight generation can call the configured LLM path and return structured output.

## Typical healthy result

A healthy run usually looks like this:

- `health.ai.llmProvider = qwen`
- `upload.skillCount > 0`
- `upload.projectCount > 0`
- `matches.count > 0`
- `gap.insightCount = 3`

If `direct` works but `upload` fails, the problem is usually in the backend API layer, file parsing, or stored resume flow.

If `upload` works but the frontend page still shows no result, the problem is usually on the frontend fetch or page-state side rather than the LLM itself.

## Failure patterns

### Qwen timeout

Symptoms:

- API returns an error like `Qwen chat request timed out after ... seconds.`

Meaning:

- The backend reached DashScope, but the model response did not complete before the configured timeout.

Recommended checks:

- Increase `DASHSCOPE_TIMEOUT_SEC`.
- Retry with a shorter resume.
- Check whether the current model is overloaded or rate-limited.

### Network / permission error in `direct`

Symptoms:

- Errors such as socket permission issues or `URLError`.

Meaning:

- The local terminal environment cannot access DashScope even if another process might.

Recommended checks:

- Confirm whether the machine, proxy, firewall, or sandbox policy allows outbound HTTPS requests.
- Compare `direct` mode and `upload` mode results to isolate environment differences.

### Upload succeeds but `matches.count = 0`

Meaning:

- Resume extraction succeeded, but no seeded jobs passed recall or filtering.

Recommended checks:

- Confirm startup seed data loaded correctly.
- Reduce strict filtering assumptions if this is unexpected.
- Try a resume that is closer to the seeded job set.

### Resume page shows no result

Meaning:

- Either upload failed and the frontend now surfaces the error, or the matches page could not load the stored resume by `resumeId`.

Recommended checks:

- Inspect backend logs for `/api/resumes/upload`.
- Re-run the script in `upload` mode using the same backend instance.

## Logic covered by this script

Using `--mode direct` verifies:

- Real DashScope / Qwen connectivity.
- LLM request composition.
- LLM JSON response parsing.
- Resume normalization.

Using `--mode upload` verifies:

- Resume upload API.
- Multipart handling.
- Resume parsing and processing service.
- LLM-based resume extraction.
- Resume persistence and lookup by `resumeId`.
- Matching API.
- Gap analysis API.

Using `--mode both` verifies:

- The real LLM itself is reachable.
- The backend upload chain also works end to end.

## Suggested test order

1. Run `direct` first to confirm Qwen is reachable.
2. Run `upload` to confirm backend flow is healthy.
3. Open the frontend and manually upload a real resume.
4. If frontend behavior differs from the script result, debug the frontend separately.
