import Link from "next/link";

import { RadarPlaceholder } from "@/components/charts/radar-placeholder";
import { AppShell } from "@/components/layout/app-shell";
import { ScorePill } from "@/components/sections/score-pill";
import { SectionCard } from "@/components/sections/section-card";
import { getGapReport, getMatchOverview, getResumePreview } from "@/lib/api";
import type { JobProfile, ResumeProfile } from "@/types/domain";

function normalizeParam(value: string | string[] | undefined): string | undefined {
  return Array.isArray(value) ? value[0] : value;
}

function getResumeSummary(resume: ResumeProfile): string {
  return resume.basicInfo.summary ?? resume.basicInfo.selfEvaluation ?? "候选人简历摘要待补充。";
}

function getResumeSkillNames(resume: ResumeProfile): string[] {
  return resume.skills.map((skill) => skill.name);
}

function getJobSummary(job: JobProfile): string {
  return job.basicInfo.summary ?? job.basicInfo.responsibilities?.join("；") ?? "岗位说明待补充。";
}

type MatchesPageProps = {
  searchParams?: Promise<Record<string, string | string[] | undefined>>;
};

export default async function MatchesPage({ searchParams }: MatchesPageProps) {
  const resolvedSearchParams = (await searchParams) ?? {};
  const resumeId = normalizeParam(resolvedSearchParams.resumeId) ?? "demo-resume";
  const [resume, matches, report] = await Promise.all([
    getResumePreview(resumeId),
    getMatchOverview(resumeId),
    getGapReport(resumeId),
  ]);
  const leadMatch = matches[0] ?? null;
  const resumeSkills = getResumeSkillNames(resume);
  const resumeSummary = getResumeSummary(resume);

  return (
    <AppShell activePath="/matches">
      <SectionCard
        title="候选人画像"
        description="当前结果页根据 resumeId 拉取结构化简历、匹配结果和 Gap 报告。"
        accent={<span className="accent-score">{resume.id}</span>}
      >
        <div className="resume-overview">
          <div>
            <p className="eyebrow">当前简历</p>
            <h3>{resume.basicInfo.name}</h3>
            <p>{resumeSummary}</p>
            {resume.basicInfo.currentTitle ? <p>当前职级：{resume.basicInfo.currentTitle}</p> : null}
            {resume.basicInfo.currentCity ? <p>当前城市：{resume.basicInfo.currentCity}</p> : null}
            {resume.sourceFileName ? <p>来源文件：{resume.sourceFileName}</p> : null}
            {resume.sourceObjectKey ? <p>对象存储键：{resume.sourceObjectKey}</p> : null}
          </div>
          <div className="pill-row">
            <ScorePill label="工作年限" value={Math.min((resume.basicInfo.workYears ?? 0) / 10, 1)} />
            <ScorePill label="技能数量" value={Math.min(resumeSkills.length / 10, 1)} />
            <ScorePill label="目标薪资" value={Math.min(resume.expectedSalary.max / 50000, 1)} />
          </div>
          <div className="tag-row">
            {resumeSkills.map((skill) => (
              <span key={skill} className="tag">
                {skill}
              </span>
            ))}
          </div>
        </div>
      </SectionCard>

      <SectionCard
        title="Top N 匹配结果"
        description="结果页展示粗排、过滤、精排之后的输出，包含可解释评分与缺口信息。"
        accent={leadMatch ? <span className="accent-score">{Math.round(leadMatch.breakdown.total * 100)}%</span> : undefined}
      >
        {leadMatch ? (
          <>
            <div className="lead-match">
              <div>
                <p className="eyebrow">最高匹配岗位</p>
                <h3>
                  {leadMatch.job.basicInfo.title} / {leadMatch.job.company}
                </h3>
                <p>{leadMatch.reasoning}</p>
              </div>
              <div className="pill-row">
                <ScorePill label="向量召回" value={leadMatch.breakdown.vectorSimilarity} />
                <ScorePill label="技能匹配" value={leadMatch.breakdown.skillMatch} />
                <ScorePill label="经验匹配" value={leadMatch.breakdown.experienceMatch} />
                <ScorePill label="教育匹配" value={leadMatch.breakdown.educationMatch} />
                <ScorePill label="薪资匹配" value={leadMatch.breakdown.salaryMatch} />
              </div>
            </div>

            <div className="match-list">
              {matches.map((match) => (
                <article key={match.job.id} className="match-card">
                  <div className="match-card-header">
                    <div>
                      <h3>{match.job.basicInfo.title}</h3>
                      <p>
                        {match.job.company} · {match.job.basicInfo.location ?? "远程"}
                      </p>
                    </div>
                    <strong>{Math.round(match.breakdown.total * 100)}%</strong>
                  </div>
                  <p>{getJobSummary(match.job)}</p>
                  <div className="pill-row">
                    <ScorePill label="技能" value={match.breakdown.skillMatch} />
                    <ScorePill label="经验" value={match.breakdown.experienceMatch} />
                    <ScorePill label="教育" value={match.breakdown.educationMatch} />
                  </div>
                  <div className="tag-row">
                    {match.matchedSkills.map((skill) => (
                      <span key={skill} className="tag">
                        {skill}
                      </span>
                    ))}
                  </div>
                  <p className="muted">
                    待补齐：{match.missingSkills.length > 0 ? match.missingSkills.join(" / ") : "当前无明显缺口"}
                  </p>
                </article>
              ))}
            </div>
          </>
        ) : (
          <div className="empty-state">
            <p>当前简历还没有可展示的匹配结果。请先确认后端服务已启动，并重新上传简历文本。</p>
            <Link href="/resume" className="primary-link">
              返回简历处理页
            </Link>
          </div>
        )}
      </SectionCard>

      <SectionCard
        title="Gap 分析"
        description="从高匹配岗位生成对照组，输出技能、经验与薪资的结构化差距。"
      >
        {matches.length > 0 ? (
          <div className="split-grid">
            <RadarPlaceholder
              values={{
                skills: leadMatch?.breakdown.skillMatch ?? 0,
                experience: leadMatch?.breakdown.experienceMatch ?? 0,
                salary: leadMatch?.breakdown.salaryMatch ?? 0,
                growth: report.missingSkills.length > 0 ? 0.82 : 0.95,
              }}
            />
            <div className="insight-list">
              <p className="eyebrow">Gap Report</p>
              <p>对照岗位：{report.baselineRoles.join(" / ")}</p>
              <p>待补技能：{report.missingSkills.join(" / ") || "暂无"}</p>
              <p>经验差距：{report.experienceGapYears} 年</p>
              <p>目标薪资差：{report.salaryGap} 元 / 月</p>
              {report.insights.map((insight) => (
                <article key={insight.dimension} className="insight-card">
                  <h3>{insight.dimension}</h3>
                  <p>{insight.currentState}</p>
                  <p>{insight.targetState}</p>
                  <p className="muted">{insight.suggestion}</p>
                </article>
              ))}
            </div>
          </div>
        ) : (
          <div className="empty-state">
            <p>Gap 分析依赖匹配结果。当前没有可用岗位对照组。</p>
          </div>
        )}
      </SectionCard>
    </AppShell>
  );
}
