import type { Route } from "next";
import Link from "next/link";

import { PageEventLogger } from "@/components/logging/page-event-logger";
import { AppShell } from "@/components/layout/app-shell";
import { ScorePill } from "@/components/sections/score-pill";
import { SectionCard } from "@/components/sections/section-card";
import { getMatchOverview, getResumePreview } from "@/lib/api";
import type {
  BonusExperience,
  BonusSkill,
  CoreExperience,
  JobProfile,
  LanguageRequirement,
  MatchResult,
  OptionalSkillGroup,
  RequiredSkill,
  ResumeProfile,
} from "@/types/domain";

const PAGE_SIZE = 8;
const PLACEHOLDER_VALUES = new Set([
  "skill pending",
  "optional skills",
  "experience pending",
  "tag pending",
  "language pending",
  "job description pending.",
  "resume summary pending.",
  "company pending",
  "untitled role",
]);

type MatchesPageProps = {
  searchParams?: Promise<Record<string, string | string[] | undefined>>;
};

function normalizeParam(value: string | string[] | undefined): string | undefined {
  return Array.isArray(value) ? value[0] : value;
}

function normalizePositiveInt(value: string | undefined, fallback: number): number {
  const parsed = Number.parseInt(value ?? "", 10);
  if (!Number.isFinite(parsed) || parsed < 1) {
    return fallback;
  }
  return parsed;
}

function buildMatchesHref(resumeId: string | undefined, page: number): Route {
  const params = new URLSearchParams();
  if (resumeId) {
    params.set("resumeId", resumeId);
  }
  if (page > 1) {
    params.set("page", String(page));
  }
  const query = params.toString();
  return (query ? `/matches?${query}` : "/matches") as Route;
}

function isMeaningfulText(value: string | null | undefined): value is string {
  const normalized = value?.trim();
  if (!normalized) {
    return false;
  }
  return !PLACEHOLDER_VALUES.has(normalized.toLowerCase());
}

function uniqueMeaningfulValues(values: Array<string | null | undefined>): string[] {
  const results: string[] = [];
  const seen = new Set<string>();
  for (const value of values) {
    if (!isMeaningfulText(value)) {
      continue;
    }
    const marker = value.toLowerCase();
    if (seen.has(marker)) {
      continue;
    }
    seen.add(marker);
    results.push(value);
  }
  return results;
}

function getResumeSummary(resume: ResumeProfile): string {
  return resume.basicInfo.summary ?? resume.basicInfo.selfEvaluation ?? "暂无简历摘要。";
}

function getResumeSkillNames(resume: ResumeProfile): string[] {
  return uniqueMeaningfulValues(resume.skills.map((skill) => skill.name));
}

function getJobSummary(job: JobProfile): string {
  if (isMeaningfulText(job.basicInfo.summary)) {
    return job.basicInfo.summary;
  }
  const responsibilities = uniqueMeaningfulValues(job.basicInfo.responsibilities ?? []);
  if (responsibilities.length > 0) {
    return responsibilities.join(" / ");
  }
  return "暂无岗位说明。";
}

function formatCompactRange(minValue?: number | null, maxValue?: number | null, suffix: string = ""): string | null {
  const left = minValue ?? null;
  const right = maxValue ?? null;
  if (left === null && right === null) {
    return null;
  }
  if (left !== null && right !== null) {
    return left === right ? `${left}${suffix}` : `${left}-${right}${suffix}`;
  }
  const fallback = left ?? right;
  return fallback === null ? null : `${fallback}${suffix}`;
}

function formatSalary(job: JobProfile): string {
  if (job.basicInfo.salaryNegotiable) {
    return "薪资面议";
  }
  const currency = isMeaningfulText(job.basicInfo.currency) ? job.basicInfo.currency : "CNY";
  const salaryRange = formatCompactRange(job.basicInfo.salaryMin, job.basicInfo.salaryMax, ` ${currency}`);
  const internRange = formatCompactRange(
    job.basicInfo.internSalaryAmount,
    job.basicInfo.internSalaryAmount,
    job.basicInfo.internSalaryUnit ? ` ${job.basicInfo.internSalaryUnit}` : "",
  );
  const months = formatCompactRange(job.basicInfo.salaryMonthsMin, job.basicInfo.salaryMonthsMax, " 薪");
  const primary = salaryRange ?? internRange;
  if (primary && months) {
    return `${primary} / ${months}`;
  }
  return primary ?? months ?? "暂无薪资信息";
}

function formatLocation(job: JobProfile): string {
  return isMeaningfulText(job.basicInfo.location) ? job.basicInfo.location : "远程 / 未注明";
}

function formatJobType(job: JobProfile): string {
  return isMeaningfulText(job.basicInfo.jobType) ? job.basicInfo.jobType : "未注明";
}

function formatRequiredSkill(skill: RequiredSkill): string {
  const extras = [
    skill.level ? `级别 ${skill.level}` : null,
    skill.minYears != null ? `${skill.minYears} 年+` : null,
    skill.description,
  ].filter(isMeaningfulText);
  return extras.length > 0 ? `${skill.name} / ${extras.join(" / ")}` : skill.name;
}

function formatOptionalGroup(group: OptionalSkillGroup): { title: string; skills: string[] } {
  const title = isMeaningfulText(group.groupName) ? group.groupName : "可选技能组";
  const skills = group.skills
    .map((skill) => {
      if (!isMeaningfulText(skill.name)) {
        return null;
      }
      const extras = [skill.level ? `级别 ${skill.level}` : null, skill.description].filter(isMeaningfulText);
      return extras.length > 0 ? `${skill.name} / ${extras.join(" / ")}` : skill.name;
    })
    .filter((value): value is string => Boolean(value));
  const minRequired = group.minRequired > 1 ? `至少满足 ${group.minRequired} 项` : "至少满足 1 项";
  return {
    title: `${title} / ${minRequired}`,
    skills,
  };
}

function formatBonusSkill(skill: BonusSkill): string {
  const extras = [
    skill.weight != null ? `权重 ${skill.weight}` : null,
    skill.description,
  ].filter(isMeaningfulText);
  return extras.length > 0 ? `${skill.name} / ${extras.join(" / ")}` : skill.name;
}

function formatExperienceItem(item: CoreExperience | BonusExperience): string {
  const extras = [
    isMeaningfulText(item.type) ? `类型 ${item.type}` : null,
    "minYears" in item && item.minYears != null ? `${item.minYears} 年+` : null,
    ...uniqueMeaningfulValues(item.keywords ?? []).map((keyword) => `关键词 ${keyword}`),
    "weight" in item && item.weight != null ? `权重 ${item.weight}` : null,
    item.description,
  ].filter(isMeaningfulText);
  return extras.length > 0 ? `${item.name} / ${extras.join(" / ")}` : item.name;
}

function formatLanguageRequirement(language: LanguageRequirement): string {
  const extras = [language.level ? `等级 ${language.level}` : null, language.required ? "必填" : "加分"].filter(
    isMeaningfulText,
  );
  return extras.length > 0 ? `${language.language} / ${extras.join(" / ")}` : language.language;
}

function formatPercent(value: number): string {
  return `${Math.round(value * 100)}%`;
}

function getFilteredMatchedSkills(match: MatchResult): string[] {
  return uniqueMeaningfulValues(match.matchedSkills);
}

function getFilteredMissingSkills(match: MatchResult): string[] {
  return uniqueMeaningfulValues(match.missingSkills);
}

export default async function MatchesPage({ searchParams }: MatchesPageProps) {
  const resolvedSearchParams = (await searchParams) ?? {};
  const resumeId = normalizeParam(resolvedSearchParams.resumeId);
  const currentPage = normalizePositiveInt(normalizeParam(resolvedSearchParams.page), 1);
  const requestedTopK = currentPage * PAGE_SIZE + 1;

  const [resume, matches] = await Promise.all([
    getResumePreview(resumeId),
    getMatchOverview(resumeId, requestedTopK),
  ]);

  const offset = (currentPage - 1) * PAGE_SIZE;
  const pageMatches = matches.slice(offset, offset + PAGE_SIZE);
  const hasNextPage = matches.length > offset + PAGE_SIZE;
  const hasPrevPage = currentPage > 1;
  const visibleStart = pageMatches.length > 0 ? offset + 1 : 0;
  const visibleEnd = pageMatches.length > 0 ? offset + pageMatches.length : 0;
  const resumeSkills = resume ? getResumeSkillNames(resume) : [];
  const resumeSummary = resume ? getResumeSummary(resume) : "";

  return (
    <AppShell activePath="/matches">
      <PageEventLogger
        event="page.matches.view"
        payload={{
          route: "/matches",
          resumeId: resumeId ?? null,
          resumeFound: Boolean(resume),
          currentPage,
          pageSize: PAGE_SIZE,
          fetchedMatchesCount: matches.length,
          visibleMatchesCount: pageMatches.length,
          hasNextPage,
        }}
      />
      <SectionCard title="简历概览" description="展示当前简历的核心信息。">
        {resume ? (
          <div className="resume-overview">
            <div>
              <p className="eyebrow">当前简历</p>
              <h3>{resume.basicInfo.name}</h3>
              <p>{resumeSummary}</p>
              {resume.basicInfo.currentTitle ? <p>当前职位：{resume.basicInfo.currentTitle}</p> : null}
              {resume.basicInfo.currentCity ? <p>所在城市：{resume.basicInfo.currentCity}</p> : null}
              {resume.sourceFileName ? <p>文件名：{resume.sourceFileName}</p> : null}
            </div>
            <div className="tag-row">
              {resumeSkills.map((skill) => (
                <span key={skill} className="tag">
                  {skill}
                </span>
              ))}
            </div>
          </div>
        ) : (
          <div className="empty-state">
            <p>当前没有可展示的简历结果。请先上传一份真实简历，再通过带有 resumeId 的链接进入结果页。</p>
            <Link href="/resume" className="primary-link">
              去上传简历
            </Link>
          </div>
        )}
      </SectionCard>

      <SectionCard title="推荐岗位" description="按匹配分从高到低展示。点击卡片可查看完整岗位信息与匹配明细。">
        {pageMatches.length > 0 ? (
          <div className="match-stack">
            <div className="pagination-bar">
              <p className="muted">
                当前第 {currentPage} 页，每页 {PAGE_SIZE} 个结果。当前展示第 {visibleStart}-{visibleEnd} 条。
              </p>
              <div className="pagination-actions">
                {hasPrevPage ? (
                  <Link href={buildMatchesHref(resumeId, currentPage - 1)} className="pagination-link">
                    上一页
                  </Link>
                ) : (
                  <span className="pagination-link pagination-link-disabled">上一页</span>
                )}
                {hasNextPage ? (
                  <Link href={buildMatchesHref(resumeId, currentPage + 1)} className="pagination-link">
                    下一页
                  </Link>
                ) : (
                  <span className="pagination-link pagination-link-disabled">下一页</span>
                )}
              </div>
            </div>

            {pageMatches.map((match, index) => {
              const requiredSkills = match.job.skillRequirements.required.filter((skill) => isMeaningfulText(skill.name));
              const optionalGroups = match.job.skillRequirements.optionalGroups
                .map(formatOptionalGroup)
                .filter((group) => group.skills.length > 0);
              const bonusSkills = match.job.skillRequirements.bonus.filter((skill) => isMeaningfulText(skill.name));
              const coreExperiences = match.job.experienceRequirements.core.filter((item) => isMeaningfulText(item.name));
              const bonusExperiences = match.job.experienceRequirements.bonus.filter((item) => isMeaningfulText(item.name));
              const responsibilities = uniqueMeaningfulValues(match.job.basicInfo.responsibilities ?? []);
              const highlights = uniqueMeaningfulValues(match.job.basicInfo.highlights ?? []);
              const matchedSkills = getFilteredMatchedSkills(match);
              const missingSkills = getFilteredMissingSkills(match);
              const tags = uniqueMeaningfulValues(match.job.tags.map((tag) => tag.name));
              const preferDegrees = uniqueMeaningfulValues(match.job.educationConstraints.preferDegrees ?? []);
              const requiredMajors = uniqueMeaningfulValues(match.job.educationConstraints.requiredMajors ?? []);
              const preferredMajors = uniqueMeaningfulValues(match.job.educationConstraints.preferredMajors ?? []);
              const certifications = uniqueMeaningfulValues(match.job.educationConstraints.certifications ?? []);
              const otherConstraints = uniqueMeaningfulValues(match.job.educationConstraints.other ?? []);
              const languages = (match.job.educationConstraints.languages ?? []).filter((item) => isMeaningfulText(item.language));
              const visibleIndex = offset + index + 1;

              return (
                <details key={match.job.id} className="job-detail-card">
                  <summary className="job-card-summary">
                    <div className="job-card-summary-main">
                      <div className="job-card-title-block">
                        <p className="eyebrow">岗位 {visibleIndex}</p>
                        <h3>{match.job.basicInfo.title}</h3>
                        <p>
                          {match.job.company} / {formatLocation(match.job)} / {formatJobType(match.job)}
                        </p>
                      </div>
                      <div className="job-card-score">
                        <span>综合匹配</span>
                        <strong>{formatPercent(match.breakdown.total)}</strong>
                      </div>
                    </div>
                    <p className="job-card-summary-text">{getJobSummary(match.job)}</p>
                    <div className="pill-row">
                      <ScorePill label="技能契合" value={match.breakdown.skillMatch} />
                      <ScorePill label="经验契合" value={match.breakdown.experienceMatch} />
                      <ScorePill label="学历契合" value={match.breakdown.educationMatch} />
                      <ScorePill label="薪资契合" value={match.breakdown.salaryMatch} />
                    </div>
                    {matchedSkills.length > 0 ? (
                      <div className="job-chip-row">
                        {matchedSkills.slice(0, 8).map((skill) => (
                          <span key={`${match.job.id}-${skill}`} className="tag">
                            {skill}
                          </span>
                        ))}
                      </div>
                    ) : null}
                    <p className="job-expand-hint">展开查看岗位详情、职责、要求和匹配明细</p>
                  </summary>

                  <div className="job-detail-panel">
                    <section className="job-detail-section">
                      <h4>岗位概览</h4>
                      <div className="job-meta-grid">
                        <div className="job-meta-item">
                          <span>公司</span>
                          <strong>{match.job.company}</strong>
                        </div>
                        <div className="job-meta-item">
                          <span>地点</span>
                          <strong>{formatLocation(match.job)}</strong>
                        </div>
                        <div className="job-meta-item">
                          <span>岗位类型</span>
                          <strong>{formatJobType(match.job)}</strong>
                        </div>
                        <div className="job-meta-item">
                          <span>薪资</span>
                          <strong>{formatSalary(match.job)}</strong>
                        </div>
                        <div className="job-meta-item">
                          <span>部门</span>
                          <strong>{isMeaningfulText(match.job.basicInfo.department) ? match.job.basicInfo.department : "未注明"}</strong>
                        </div>
                        <div className="job-meta-item">
                          <span>经验年限</span>
                          <strong>
                            {formatCompactRange(
                              match.job.experienceRequirements.minTotalYears,
                              match.job.experienceRequirements.maxTotalYears,
                              " 年",
                            ) ?? "未注明"}
                          </strong>
                        </div>
                      </div>
                    </section>

                    <section className="job-detail-section">
                      <h4>岗位说明</h4>
                      <div className="job-subsection">
                        <h5>岗位摘要</h5>
                        <p>{getJobSummary(match.job)}</p>
                      </div>
                      {responsibilities.length > 0 ? (
                        <div className="job-subsection">
                          <h5>岗位职责</h5>
                          <ul className="job-detail-list">
                            {responsibilities.map((item) => (
                              <li key={item}>{item}</li>
                            ))}
                          </ul>
                        </div>
                      ) : null}
                      {highlights.length > 0 ? (
                        <div className="job-subsection">
                          <h5>亮点信息</h5>
                          <ul className="job-detail-list">
                            {highlights.map((item) => (
                              <li key={item}>{item}</li>
                            ))}
                          </ul>
                        </div>
                      ) : null}
                    </section>

                    <section className="job-detail-section">
                      <h4>技能要求</h4>
                      {requiredSkills.length > 0 ? (
                        <div className="job-subsection">
                          <h5>必需技能</h5>
                          <ul className="job-detail-list">
                            {requiredSkills.map((skill) => (
                              <li key={`${match.job.id}-required-${skill.name}`}>{formatRequiredSkill(skill)}</li>
                            ))}
                          </ul>
                        </div>
                      ) : null}
                      {optionalGroups.length > 0 ? (
                        <div className="job-subsection">
                          <h5>可选技能组</h5>
                          <div className="job-section-stack">
                            {optionalGroups.map((group) => (
                              <div key={`${match.job.id}-${group.title}`}>
                                <p className="muted">{group.title}</p>
                                <ul className="job-detail-list">
                                  {group.skills.map((skill) => (
                                    <li key={`${group.title}-${skill}`}>{skill}</li>
                                  ))}
                                </ul>
                              </div>
                            ))}
                          </div>
                        </div>
                      ) : null}
                      {bonusSkills.length > 0 ? (
                        <div className="job-subsection">
                          <h5>加分技能</h5>
                          <ul className="job-detail-list">
                            {bonusSkills.map((skill) => (
                              <li key={`${match.job.id}-bonus-${skill.name}`}>{formatBonusSkill(skill)}</li>
                            ))}
                          </ul>
                        </div>
                      ) : null}
                      {requiredSkills.length === 0 && optionalGroups.length === 0 && bonusSkills.length === 0 ? (
                        <p className="muted">当前岗位暂无可展示的结构化技能要求。</p>
                      ) : null}
                    </section>

                    <section className="job-detail-section">
                      <h4>经验要求</h4>
                      <div className="job-meta-grid">
                        <div className="job-meta-item">
                          <span>最低总年限</span>
                          <strong>
                            {match.job.experienceRequirements.minTotalYears != null
                              ? `${match.job.experienceRequirements.minTotalYears} 年`
                              : "未注明"}
                          </strong>
                        </div>
                        <div className="job-meta-item">
                          <span>最高总年限</span>
                          <strong>
                            {match.job.experienceRequirements.maxTotalYears != null
                              ? `${match.job.experienceRequirements.maxTotalYears} 年`
                              : "未注明"}
                          </strong>
                        </div>
                      </div>
                      {coreExperiences.length > 0 ? (
                        <div className="job-subsection">
                          <h5>核心经验</h5>
                          <ul className="job-detail-list">
                            {coreExperiences.map((item) => (
                              <li key={`${match.job.id}-core-${item.name}`}>{formatExperienceItem(item)}</li>
                            ))}
                          </ul>
                        </div>
                      ) : null}
                      {bonusExperiences.length > 0 ? (
                        <div className="job-subsection">
                          <h5>加分经验</h5>
                          <ul className="job-detail-list">
                            {bonusExperiences.map((item) => (
                              <li key={`${match.job.id}-bonus-exp-${item.name}`}>{formatExperienceItem(item)}</li>
                            ))}
                          </ul>
                        </div>
                      ) : null}
                      {coreExperiences.length === 0 && bonusExperiences.length === 0 ? (
                        <p className="muted">当前岗位暂无可展示的结构化经验要求。</p>
                      ) : null}
                    </section>

                    <section className="job-detail-section">
                      <h4>教育与附加约束</h4>
                      <div className="job-meta-grid">
                        <div className="job-meta-item">
                          <span>最低学历</span>
                          <strong>{isMeaningfulText(match.job.educationConstraints.minDegree) ? match.job.educationConstraints.minDegree : "未注明"}</strong>
                        </div>
                        <div className="job-meta-item">
                          <span>偏好学历</span>
                          <strong>{preferDegrees.length > 0 ? preferDegrees.join(" / ") : "未注明"}</strong>
                        </div>
                        <div className="job-meta-item">
                          <span>必需专业</span>
                          <strong>{requiredMajors.length > 0 ? requiredMajors.join(" / ") : "未注明"}</strong>
                        </div>
                        <div className="job-meta-item">
                          <span>偏好专业</span>
                          <strong>{preferredMajors.length > 0 ? preferredMajors.join(" / ") : "未注明"}</strong>
                        </div>
                        <div className="job-meta-item">
                          <span>证书要求</span>
                          <strong>{certifications.length > 0 ? certifications.join(" / ") : "未注明"}</strong>
                        </div>
                        <div className="job-meta-item">
                          <span>年龄范围</span>
                          <strong>{isMeaningfulText(match.job.educationConstraints.ageRange) ? match.job.educationConstraints.ageRange : "未注明"}</strong>
                        </div>
                      </div>
                      {languages.length > 0 ? (
                        <div className="job-subsection">
                          <h5>语言要求</h5>
                          <ul className="job-detail-list">
                            {languages.map((item) => (
                              <li key={`${match.job.id}-${item.language}`}>{formatLanguageRequirement(item)}</li>
                            ))}
                          </ul>
                        </div>
                      ) : null}
                      {otherConstraints.length > 0 ? (
                        <div className="job-subsection">
                          <h5>其他约束</h5>
                          <ul className="job-detail-list">
                            {otherConstraints.map((item) => (
                              <li key={`${match.job.id}-${item}`}>{item}</li>
                            ))}
                          </ul>
                        </div>
                      ) : null}
                    </section>

                    <section className="job-detail-section">
                      <h4>匹配明细</h4>
                      <div className="pill-row">
                        <ScorePill label="综合匹配" value={match.breakdown.total} />
                        <ScorePill label="向量召回" value={match.breakdown.vectorSimilarity} />
                        <ScorePill label="技能契合" value={match.breakdown.skillMatch} />
                        <ScorePill label="经验契合" value={match.breakdown.experienceMatch} />
                        <ScorePill label="学历契合" value={match.breakdown.educationMatch} />
                        <ScorePill label="薪资契合" value={match.breakdown.salaryMatch} />
                      </div>
                      <div className="job-subsection">
                        <h5>已命中技能</h5>
                        <p>{matchedSkills.length > 0 ? matchedSkills.join(" / ") : "暂无明显命中技能"}</p>
                      </div>
                      <div className="job-subsection">
                        <h5>缺少技能</h5>
                        <p>{missingSkills.length > 0 ? missingSkills.join(" / ") : "暂无明显缺口"}</p>
                      </div>
                      <div className="job-subsection">
                        <h5>系统说明</h5>
                        <p>{match.reasoning}</p>
                      </div>
                    </section>

                    {tags.length > 0 ? (
                      <section className="job-detail-section">
                        <h4>岗位标签</h4>
                        <div className="job-chip-row">
                          {tags.map((tag) => (
                            <span key={`${match.job.id}-${tag}`} className="tag">
                              {tag}
                            </span>
                          ))}
                        </div>
                      </section>
                    ) : null}
                  </div>
                </details>
              );
            })}

            <div className="pagination-bar">
              <p className="muted">结果按综合匹配分降序排列。翻页会继续请求更多候选结果。</p>
              <div className="pagination-actions">
                {hasPrevPage ? (
                  <Link href={buildMatchesHref(resumeId, currentPage - 1)} className="pagination-link">
                    上一页
                  </Link>
                ) : (
                  <span className="pagination-link pagination-link-disabled">上一页</span>
                )}
                {hasNextPage ? (
                  <Link href={buildMatchesHref(resumeId, currentPage + 1)} className="pagination-link">
                    下一页
                  </Link>
                ) : (
                  <span className="pagination-link pagination-link-disabled">下一页</span>
                )}
              </div>
            </div>
          </div>
        ) : (
          <div className="empty-state">
            {matches.length > 0 && hasPrevPage ? (
              <>
                <p>当前页没有可展示的结果。请返回上一页查看已加载内容。</p>
                <Link href={buildMatchesHref(resumeId, currentPage - 1)} className="primary-link">
                  返回上一页
                </Link>
              </>
            ) : (
              <>
                <p>当前没有可展示的匹配结果。通常意味着简历尚未上传、后台岗位库尚未准备好，或召回后的岗位都为空。</p>
                <Link href="/resume" className="primary-link">
                  返回上传页
                </Link>
              </>
            )}
          </div>
        )}
      </SectionCard>
    </AppShell>
  );
}


