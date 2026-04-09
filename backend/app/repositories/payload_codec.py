from __future__ import annotations

from typing import Any

from app.domain.models import (
    BonusExperience,
    BonusSkill,
    CoreExperience,
    build_job_standard_tags,
    JobFilterFacets,
    JobBasicInfo,
    JobEducationConstraints,
    JobExperienceRequirements,
    JobProfile,
    JobSkillRequirements,
    JobTag,
    LanguageRequirement,
    OptionalSkill,
    OptionalSkillGroup,
    RequiredSkill,
    ResumeBasicInfo,
    ResumeEducation,
    ResumeFilterFacets,
    ResumeProfile,
    ResumeProject,
    ResumeSkill,
    ResumeTag,
    ResumeWorkExperience,
    SalaryRange,
    build_job_filter_facets,
    build_resume_filter_facets,
)


def resume_from_payload(payload: dict[str, Any]) -> ResumeProfile:
    filter_facets_payload = payload.get("filter_facets") or {}
    resume = ResumeProfile(
        id=str(payload.get("id") or ""),
        basic_info=ResumeBasicInfo(**(payload.get("basic_info") or {})),
        educations=[ResumeEducation(**item) for item in payload.get("educations") or []],
        work_experiences=[ResumeWorkExperience(**item) for item in payload.get("work_experiences") or []],
        projects=[ResumeProject(**item) for item in payload.get("projects") or []],
        skills=[ResumeSkill(**item) for item in payload.get("skills") or []],
        tags=[ResumeTag(**item) for item in payload.get("tags") or []],
        expected_salary=SalaryRange(**(payload.get("expected_salary") or {"min": 0, "max": 0, "currency": "CNY"})),
        filter_facets=ResumeFilterFacets(**filter_facets_payload) if filter_facets_payload else ResumeFilterFacets(),
        is_resume=payload.get("is_resume"),
        raw_text=str(payload.get("raw_text") or ""),
        source_file_name=str(payload.get("source_file_name") or ""),
        source_content_type=str(payload.get("source_content_type") or ""),
        source_object_key=str(payload.get("source_object_key") or ""),
    )
    resume.tags = [tag for tag in resume.tags if not getattr(tag, "filterable", False)] + build_resume_standard_tags(resume)
    if not filter_facets_payload:
        resume.filter_facets = build_resume_filter_facets(resume)
    return resume


def job_from_payload(payload: dict[str, Any]) -> JobProfile:
    skill_requirements = payload.get("skill_requirements") or {}
    experience_requirements = payload.get("experience_requirements") or {}
    education_constraints = payload.get("education_constraints") or {}
    basic_info_payload = payload.get("basic_info") or {"title": "Untitled Role"}
    tags = [JobTag(**item) for item in payload.get("tags") or []]
    tags = [tag for tag in tags if not getattr(tag, "filterable", False)] + build_job_standard_tags(
        title=str(basic_info_payload.get("title") or "Untitled Role"),
        location=basic_info_payload.get("location"),
        job_type=basic_info_payload.get("job_type"),
        summary=basic_info_payload.get("summary"),
        tags=tags,
        min_total_years=experience_requirements.get("min_total_years"),
        max_total_years=experience_requirements.get("max_total_years"),
        salary_min=basic_info_payload.get("salary_min"),
        salary_max=basic_info_payload.get("salary_max"),
        intern_salary_amount=basic_info_payload.get("intern_salary_amount"),
    )
    filter_facets_payload = payload.get("filter_facets") or {}
    return JobProfile(
        id=str(payload.get("id") or ""),
        company=str(payload.get("company") or "Company Pending"),
        basic_info=JobBasicInfo(**basic_info_payload),
        skill_requirements=JobSkillRequirements(
            required=[RequiredSkill(**item) for item in skill_requirements.get("required") or []],
            optional_groups=[
                OptionalSkillGroup(
                    group_name=str(item.get("group_name") or "Optional Skills"),
                    description=item.get("description"),
                    min_required=int(item.get("min_required", 1)),
                    skills=[OptionalSkill(**skill) for skill in item.get("skills") or []],
                )
                for item in skill_requirements.get("optional_groups") or []
            ],
            bonus=[BonusSkill(**item) for item in skill_requirements.get("bonus") or []],
        ),
        experience_requirements=JobExperienceRequirements(
            core=[CoreExperience(**item) for item in experience_requirements.get("core") or []],
            bonus=[BonusExperience(**item) for item in experience_requirements.get("bonus") or []],
            min_total_years=experience_requirements.get("min_total_years"),
            max_total_years=experience_requirements.get("max_total_years"),
        ),
        education_constraints=JobEducationConstraints(
            min_degree=education_constraints.get("min_degree"),
            prefer_degrees=list(education_constraints.get("prefer_degrees") or []),
            required_majors=list(education_constraints.get("required_majors") or []),
            preferred_majors=list(education_constraints.get("preferred_majors") or []),
            languages=[LanguageRequirement(**item) for item in education_constraints.get("languages") or []],
            certifications=list(education_constraints.get("certifications") or []),
            age_range=education_constraints.get("age_range"),
            other=list(education_constraints.get("other") or []),
        ),
        tags=tags,
        filter_facets=(
            JobFilterFacets(**filter_facets_payload)
            if filter_facets_payload
            else build_job_filter_facets(
                title=str(basic_info_payload.get("title") or "Untitled Role"),
                location=basic_info_payload.get("location"),
                job_type=basic_info_payload.get("job_type"),
                summary=basic_info_payload.get("summary"),
                min_total_years=experience_requirements.get("min_total_years"),
                max_total_years=experience_requirements.get("max_total_years"),
                tags=tags,
                raw_posted_at_values=[payload.get(field_name) for field_name in ("posted_at", "created_at", "updated_at")],
            )
        ),
    )
