test_resume_algorithm_llm_compare.py

Option 1: set local defaults in `backend/test/local_test_config.py`

```python
LOCAL_TEST_CONFIG.resume.default_resume_id = ""
LOCAL_TEST_CONFIG.resume.default_resume_file = r"backend\uploads\resumes\resume-19900b96\bdee99ac_15-24K_10.pdf"
LOCAL_TEST_CONFIG.resume.default_resume_ids = []
```

Then run without a long resume argument:

```bash
python backend\test\test_resume_algorithm_llm_compare.py
```

CLI arguments still override the local config.

Option 2: keep using CLI arguments:

```bash
python backend\test\test_resume_algorithm_llm_compare.py --resume-file backend\uploads\resumes\resume-19900b96\bdee99ac_15-24K_10.pdf
```

Resume defaults and rerank model switching:

`docs/resume_algorithm_llm_compare_rerank_config.md`
