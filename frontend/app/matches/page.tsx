import Link from "next/link";

import { AppShell } from "@/components/layout/app-shell";
import { ScorePill } from "@/components/sections/score-pill";
import { SectionCard } from "@/components/sections/section-card";
import { getGapReport, getMatchOverview, getResumePreview } from "@/lib/api";
import type { JobProfile, ResumeProfile } from "@/types/domain";

function normalizeParam(value: string | string[] | undefined): string | undefined {
  return Array.isArray(value) ? value[0] : value;
}

function getResumeSummary(resume: ResumeProfile): string {
  return resume.basicInfo.summary ?? resume.basicInfo.selfEvaluation ?? "暂无简历摘要。";
}

function getResumeSkillNames(resume: ResumeProfile): string[] {
  return resume.skills.map((skill) => skill.name);
}

function getJobSummary(job: JobProfile): string {
  return job.basicInfo.summary ?? job.basicInfo.responsibilities?.join(" / ") ?? "暂无岗位说明。";
}

type MatchesPageProps = {
  searchParams?: Promise<Record<string, string | string[] | undefined>>;
};

export default async function MatchesPage({ searchParams }: MatchesPageProps) {
  const resolvedSearchParams = (await searchParams) ?? {};
  const resumeId = normalizeParam(resolvedSearchParams.resumeId);
  const [resume, matches, report] = await Promise.all([
    getResumePreview(resumeId),
    getMatchOverview(resumeId),
    getGapReport(resumeId),
  ]);

  const leadMatch = matches[0] ?? null;
  const resumeSkills = resume ? getResumeSkillNames(resume) : [];
  const resumeSummary = resume ? getResumeSummary(resume) : "";

  return (
    <AppShell activePath="/matches">
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
            <div className="pill-row">
              <ScorePill label="工作年限" value={Math.min((resume.basicInfo.workYears ?? 0) / 10, 1)} />
              <ScorePill label="技能数量" value={Math.min(resumeSkills.length / 10, 1)} />
              <ScorePill label="期望薪资" value={Math.min(resume.expectedSalary.max / 50000, 1)} />
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

      <SectionCard
        title="推荐岗位"
        description="按当前简历筛选出的岗位结果。"
        accent={leadMatch ? <span className="accent-score">{Math.round(leadMatch.breakdown.total * 100)}%</span> : undefined}
      >
        {leadMatch ? (
          <div className="match-list">
            {matches.map((match) => (
              <article key={match.job.id} className="match-card">
                <div className="match-card-header">
                  <div>
                    <h3>{match.job.basicInfo.title}</h3>
                    <p>
                      {match.job.company} / {match.job.basicInfo.location ?? "远程"}
                    </p>
                  </div>
                  <strong>{Math.round(match.breakdown.total * 100)}%</strong>
                </div>
                <p>{getJobSummary(match.job)}</p>
                <div className="pill-row">
                  <ScorePill label="技能契合" value={match.breakdown.skillMatch} />
                  <ScorePill label="经验契合" value={match.breakdown.experienceMatch} />
                </div>
                {match.matchedSkills.length > 0 ? (
                  <div className="tag-row">
                    {match.matchedSkills.slice(0, 6).map((skill) => (
                      <span key={skill} className="tag">
                        {skill}
                      </span>
                    ))}
                  </div>
                ) : null}
                <p className="muted">
                  缺少技能：{match.missingSkills.length > 0 ? match.missingSkills.join(" / ") : "暂无明显缺口"}
                </p>
              </article>
            ))}
          </div>
        ) : (
          <div className="empty-state">
            <p>当前没有可展示的匹配结果。通常意味着简历尚未上传、后台岗位库尚未准备好，或召回后的岗位都被过滤掉了。</p>
            <Link href="/resume" className="primary-link">
              返回上传页
            </Link>
          </div>
        )}
      </SectionCard>

      <SectionCard title="差距分析" description="只保留用户关心的差距结论和建议。">
        {matches.length > 0 ? (
          <div className="insight-list">
            <p>对照岗位：{report.baselineRoles.join(" / ") || "暂无"}</p>
            <p>缺少技能：{report.missingSkills.join(" / ") || "暂无"}</p>
            <p>经验差距：{report.experienceGapYears} 年</p>
            <p>薪资差距：{report.salaryGap} 元 / 月</p>
            {report.insights.map((insight) => (
              <article key={insight.dimension} className="insight-card">
                <h3>{insight.dimension}</h3>
                <p>{insight.currentState}</p>
                <p>{insight.targetState}</p>
                <p className="muted">{insight.suggestion}</p>
              </article>
            ))}
          </div>
        ) : (
          <div className="empty-state">
            <p>差距分析依赖有效的匹配结果。请先上传简历，并确认后台岗位库已经准备完成。</p>
          </div>
        )}
      </SectionCard>
    </AppShell>
  );
}
