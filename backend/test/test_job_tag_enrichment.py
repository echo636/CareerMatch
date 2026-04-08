from __future__ import annotations

from pathlib import Path
import sys
import unittest

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.clients.llm import QwenLLMClient
from app.job_enrichment import build_job_context_text, infer_job_tags


class JobTagEnrichmentTestCase(unittest.TestCase):
    def test_build_job_context_text_includes_structured_fields(self) -> None:
        payload = {
            "basic_info": {
                "title": "Frontend Engineer",
                "summary": "Build visualization products.",
                "responsibilities": ["Build dashboard pages"],
                "highlights": ["Quarterly bonus"],
            },
            "skill_requirements": {
                "required": [{"name": "Vue", "description": "Build SPA"}],
                "optional_groups": [
                    {
                        "group_name": "Visualization",
                        "description": "Charts and mapping",
                        "skills": [{"name": "ECharts", "description": "Dashboard charts"}],
                    }
                ],
                "bonus": [{"name": "TypeScript", "description": "Typed frontend"}],
            },
            "experience_requirements": {
                "core": [{"name": "GIS platform", "description": "Spatial dashboard", "keywords": ["map", "dashboard"]}],
                "bonus": [],
            },
            "education_constraints": {
                "required_majors": ["Computer Science"],
                "languages": [{"language": "English", "level": "intermediate"}],
                "certifications": ["PMP"],
            },
            "tags": [{"name": "Industrial SaaS", "category": "industry"}],
        }

        context = build_job_context_text(payload)

        self.assertIn("Vue", context)
        self.assertIn("ECharts", context)
        self.assertIn("GIS platform", context)
        self.assertIn("Computer Science", context)
        self.assertIn("English", context)
        self.assertIn("Industrial SaaS", context)

    def test_infer_job_tags_builds_balanced_categories(self) -> None:
        tags = infer_job_tags(
            {
                "job_keys": "GIS, visualization",
                "company_industry": "Industrial SaaS",
                "tags": [
                    {"name": "Vue", "category": "general", "weight": 2},
                    {"name": "Remote", "category": "general", "weight": 2},
                ],
            },
            skills=["Vue", "TypeScript", "ECharts", "Vue"],
            topics=["Data Visualization Platform", "GIS Dashboard"],
            education_constraints={
                "required_majors": ["Computer Science"],
                "languages": [{"language": "English", "required": True}],
                "certifications": ["PMP"],
            },
            highlights=["Quarterly bonus", "Remote"],
        )

        tag_index = {(item["name"], item["category"]) for item in tags}

        self.assertIn(("Vue", "tech"), tag_index)
        self.assertNotIn(("Vue", "general"), tag_index)
        self.assertIn(("Data Visualization Platform", "project"), tag_index)
        self.assertIn(("GIS", "domain"), tag_index)
        self.assertIn(("Industrial SaaS", "industry"), tag_index)
        self.assertIn(("Computer Science", "education"), tag_index)
        self.assertIn(("English", "language"), tag_index)
        self.assertIn(("Quarterly bonus", "general"), tag_index)

    def test_normalize_job_rebuilds_tags_for_standardized_payload(self) -> None:
        client = QwenLLMClient(api_key="local-offline")
        payload = {
            "id": "job-1",
            "company": "Example",
            "basic_info": {
                "title": "Frontend Engineer",
                "summary": "Frontend platform role",
                "location": "Shanghai",
                "job_type": "fulltime",
                "responsibilities": ["Build dashboard pages"],
                "highlights": ["Quarterly bonus"],
            },
            "skill_requirements": {
                "required": [{"name": "Vue"}, {"name": "TypeScript"}],
                "optional_groups": [],
                "bonus": [{"name": "ECharts", "weight": 2}],
            },
            "experience_requirements": {
                "core": [{"type": "project", "name": "Data Visualization Platform", "keywords": ["GIS"]}],
                "bonus": [],
                "min_total_years": 1,
                "max_total_years": 3,
            },
            "education_constraints": {
                "required_majors": ["Computer Science"],
                "languages": [{"language": "English", "required": True}],
            },
            "tags": [{"name": "Vue", "category": "general", "weight": 1}],
        }

        normalized = client._normalize_job({}, payload)
        tag_index = {(item["name"], item["category"]) for item in normalized["tags"]}

        self.assertIn(("Vue", "tech"), tag_index)
        self.assertIn(("Data Visualization Platform", "project"), tag_index)
        self.assertIn(("Computer Science", "education"), tag_index)
        self.assertIn(("English", "language"), tag_index)
        self.assertNotIn(("Vue", "general"), tag_index)


if __name__ == "__main__":
    unittest.main()
