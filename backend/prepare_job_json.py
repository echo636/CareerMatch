from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

SKILL_ALIASES: dict[str, tuple[str, ...]] = {
    'Java': ('java',),
    'Python': ('python',),
    'Golang': ('golang', 'go'),
    'C++': ('c++',),
    'C#': ('c#', 'csharp'),
    'JavaScript': ('javascript',),
    'TypeScript': ('typescript',),
    'Node.js': ('node.js', 'nodejs'),
    'React': ('react',),
    'Vue': ('vue', 'vue.js'),
    'Angular': ('angular',),
    'HTML5': ('html5', 'html'),
    'CSS3': ('css3', 'css'),
    'Flask': ('flask',),
    'FastAPI': ('fastapi',),
    'Django': ('django',),
    'Spring': ('spring',),
    'Spring Boot': ('spring boot',),
    'MySQL': ('mysql',),
    'PostgreSQL': ('postgresql', 'postgres'),
    'Redis': ('redis',),
    'MongoDB': ('mongodb',),
    'Oracle': ('oracle',),
    'SQL': ('sql',),
    'NoSQL': ('nosql',),
    'Kafka': ('kafka',),
    'RabbitMQ': ('rabbitmq',),
    'Elasticsearch': ('elasticsearch',),
    'Docker': ('docker',),
    'Kubernetes': ('kubernetes', 'k8s'),
    'Linux': ('linux',),
    'Git': ('git',),
    'Jenkins': ('jenkins',),
    'AWS': ('aws',),
    'Azure': ('azure',),
    'GCP': ('gcp', 'google cloud'),
    'TensorFlow': ('tensorflow',),
    'PyTorch': ('pytorch',),
    'LLM': ('llm', '大模型'),
    'Embedding': ('embedding',),
    'RAG': ('rag',),
    'Prompt Design': ('prompt', '提示词'),
    'Qdrant': ('qdrant',),
    'pgvector': ('pgvector',),
    'ETL': ('etl',),
    'Selenium': ('selenium',),
    'Appium': ('appium',),
    'Playwright': ('playwright',),
    'Cypress': ('cypress',),
    'JMeter': ('jmeter',),
    'LoadRunner': ('loadrunner',),
    '自动化测试': ('自动化测试',),
    '接口测试': ('接口测试',),
    '功能测试': ('功能测试',),
    '性能测试': ('性能测试',),
    '白盒测试': ('白盒测试',),
    '黑盒测试': ('黑盒测试',),
    '测试开发': ('测试开发',),
    '数据分析': ('数据分析',),
    '微服务': ('微服务',),
    '分布式': ('分布式',),
    'TCP/IP': ('tcp/ip',),
    'Rust': ('rust',),
}
RESP_STOP_MARKERS = ['岗位要求', '任职要求', '职位要求', 'Requirements:', '任职资格']
RESP_SPLIT_PATTERN = re.compile(r'(?:^|\s*)(?:\d+[、.．]|[-•])\s*')


def clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def dedupe(values: list[str]) -> list[str]:
    results: list[str] = []
    seen: set[str] = set()
    for item in values:
        text = clean_text(item)
        if text is None:
            continue
        marker = text.lower()
        if marker in seen:
            continue
        seen.add(marker)
        results.append(text)
    return results


def normalize_degree(value: Any) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    lowered = text.lower()
    if any(token in text for token in ('博士',)) or any(token in lowered for token in ('phd', 'doctor')):
        return 'phd'
    if any(token in text for token in ('硕士', '研究生')) or any(token in lowered for token in ('master', 'graduate')):
        return 'master'
    if 'mba' in lowered:
        return 'mba'
    if any(token in text for token in ('本科', '学士')) or 'bachelor' in lowered:
        return 'bachelor'
    if any(token in text for token in ('大专', '专科')) or any(token in lowered for token in ('associate', 'college')):
        return 'associate'
    if any(token in text for token in ('高中',)) or 'high school' in lowered:
        return 'high_school'
    if text in {'不限', 'none'}:
        return None
    if any(token in text for token in ('专业', '毕业')):
        return None
    return None


def find_alias_position(text: str, alias: str) -> int:
    target = alias.lower()
    if any('\u4e00' <= ch <= '\u9fff' for ch in target):
        return text.find(target)
    pattern = re.compile(rf'(?<![a-z0-9]){re.escape(target)}(?![a-z0-9])')
    match = pattern.search(text)
    return -1 if match is None else match.start()


def collect_text_chunks(record: dict[str, Any]) -> list[str]:
    chunks = [
        record.get('title'),
        record.get('summary'),
        record.get('description'),
        *(record.get('responsibilities') or []),
    ]
    return [text for text in (clean_text(item) for item in chunks) if text]


def extract_skills(record: dict[str, Any]) -> list[str]:
    chunks = collect_text_chunks(record)
    text = '\n'.join(chunks).lower()
    matches: list[tuple[int, str]] = []

    for name, aliases in SKILL_ALIASES.items():
        best: int | None = None
        for alias in aliases:
            position = find_alias_position(text, alias)
            if position == -1:
                continue
            if best is None or position < best:
                best = position
        if best is not None:
            matches.append((best, name))

    matches.sort(key=lambda item: item[0])
    extracted = [name for _, name in matches]

    existing: list[str] = []
    existing.extend(record.get('skills') or [])
    skill_requirements = record.get('skill_requirements') or {}
    existing.extend(item.get('name') for item in skill_requirements.get('required') or [] if isinstance(item, dict))
    existing.extend(item.get('name') for item in skill_requirements.get('bonus') or [] if isinstance(item, dict))

    merged = dedupe(extracted + [item for item in existing if clean_text(item)])
    return merged[:12]


def infer_responsibilities(record: dict[str, Any]) -> list[str]:
    current = dedupe(record.get('responsibilities') or [])
    if current:
        return current[:8]

    description = clean_text(record.get('description'))
    if not description:
        return []

    source = description
    for marker in RESP_STOP_MARKERS:
        index = source.find(marker)
        if index > 0:
            source = source[:index]
            break

    parts = []
    split_values = RESP_SPLIT_PATTERN.split(source)
    if len(split_values) > 1:
        parts.extend(split_values)
    else:
        parts.extend(re.split(r'[；;\n]+', source))

    cleaned = []
    for item in parts:
        text = clean_text(item)
        if text is None or len(text) < 10:
            continue
        cleaned.append(text)
    return dedupe(cleaned)[:6]


def build_summary(record: dict[str, Any]) -> str:
    summary = clean_text(record.get('summary'))
    if summary:
        return summary
    pieces = [clean_text(record.get('description')), clean_text(record.get('title'))]
    return '\n\n'.join(item for item in pieces if item) or 'Job description pending.'


def update_skill_sections(record: dict[str, Any], skills: list[str]) -> None:
    record['skills'] = skills
    record['skill_requirements'] = {
        'required': [{'name': name} for name in skills[:3]],
        'optional_groups': [],
        'bonus': [
            {'name': name, 'weight': max(5 - index, 1)}
            for index, name in enumerate(skills[3:8])
        ],
    }
    record['tags'] = [
        {'name': name, 'category': 'tech', 'weight': 5 if index < 3 else 4}
        for index, name in enumerate(skills[:8])
    ]


def build_report(data: list[dict[str, Any]]) -> dict[str, Any]:
    company_missing = sum(1 for item in data if not item.get('company') or item.get('company') == 'Company Pending')
    location_missing = sum(1 for item in data if not item.get('location'))
    skills_missing = sum(1 for item in data if not (item.get('skills') or []))
    summary_missing = sum(1 for item in data if not item.get('summary'))
    description_missing = sum(1 for item in data if not item.get('description'))
    responsibility_missing = sum(1 for item in data if not (item.get('responsibilities') or []))
    degree_counter = Counter((item.get('education_constraints') or {}).get('min_degree') or 'none' for item in data)
    job_type_counter = Counter(item.get('job_type') or 'none' for item in data)
    source_counter = Counter(item.get('source') or 'none' for item in data)
    return {
        'count': len(data),
        'company_missing': company_missing,
        'location_missing': location_missing,
        'skills_missing': skills_missing,
        'summary_missing': summary_missing,
        'description_missing': description_missing,
        'responsibility_missing': responsibility_missing,
        'degree_distribution_top10': degree_counter.most_common(10),
        'job_type_distribution_top10': job_type_counter.most_common(10),
        'source_distribution_top10': source_counter.most_common(10),
        'sample_titles': [item.get('title') for item in data[:10]],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description='Clean and prepare job JSON records for testing.')
    parser.add_argument('--input', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--summary-output', required=False)
    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)
    summary_path = Path(args.summary_output) if args.summary_output else None

    data = json.loads(input_path.read_text(encoding='utf-8'))
    if not isinstance(data, list):
        raise ValueError('Input JSON must be a list of job records.')

    cleaned: list[dict[str, Any]] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        record = dict(item)
        record['title'] = clean_text(record.get('title')) or 'Untitled Role'
        record['company'] = clean_text(record.get('company')) or 'Company Pending'
        record['location'] = clean_text(record.get('location')) or 'Remote'
        record['job_type'] = clean_text(record.get('job_type')) or 'fulltime'
        record['summary'] = build_summary(record)
        record['description'] = clean_text(record.get('description')) or record['summary']
        record['responsibilities'] = infer_responsibilities(record)

        education = dict(record.get('education_constraints') or {})
        education['min_degree'] = normalize_degree(education.get('min_degree'))
        education['prefer_degrees'] = dedupe(education.get('prefer_degrees') or [])
        education['required_majors'] = dedupe(education.get('required_majors') or [])
        education['preferred_majors'] = dedupe(education.get('preferred_majors') or [])
        education['languages'] = education.get('languages') or []
        education['certifications'] = dedupe(education.get('certifications') or [])
        education['other'] = dedupe(education.get('other') or [])
        record['education_constraints'] = education

        skills = extract_skills(record)
        update_skill_sections(record, skills)
        cleaned.append(record)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(cleaned, ensure_ascii=False, indent=2), encoding='utf-8')

    report = build_report(cleaned)
    if summary_path is not None:
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        summary_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')

    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())


