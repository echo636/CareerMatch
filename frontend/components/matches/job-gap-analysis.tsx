import type { MatchResult, ResumeProfile, ResumeSkill } from "@/types/domain";

type JobGapInsight = {
  dimension: string;
  currentState: string;
  targetState: string;
  suggestion: string;
};

type JobGapAnalysisProps = {
  match: MatchResult;
  resume: ResumeProfile;
};

export function JobGapAnalysis({ match, resume }: JobGapAnalysisProps) {
  const analysis = buildJobGapAnalysis(match, resume);

  return (
    <section className="job-detail-section">
      <h4>差距分析</h4>
      <div className="gap-stat-grid">
        <article className="gap-stat-card">
          <span>缺口技能</span>
          <strong>{analysis.missingSkills.length}</strong>
        </article>
        <article className="gap-stat-card">
          <span>经验差距</span>
          <strong>{analysis.experienceGapYears > 0 ? `${analysis.experienceGapYears} 年` : "已覆盖"}</strong>
        </article>
        <article className="gap-stat-card">
          <span>薪资状态</span>
          <strong>{analysis.salaryStatus}</strong>
        </article>
        <article className="gap-stat-card">
          <span>已命中技能</span>
          <strong>{analysis.matchedSkills.length}</strong>
        </article>
      </div>

      <div className="job-subsection">
        <h5>待补技能</h5>
        {analysis.missingSkills.length > 0 ? (
          <div className="job-chip-row">
            {analysis.missingSkills.map((skill) => (
              <span key={`${match.job.id}-gap-${skill}`} className="tag">
                {skill}
              </span>
            ))}
          </div>
        ) : (
          <p>当前简历对这个岗位的核心技能覆盖已经比较完整。</p>
        )}
      </div>

      <div className="insight-list">
        {analysis.insights.map((insight) => (
          <article key={`${match.job.id}-${insight.dimension}`} className="insight-card">
            <p className="eyebrow">{insight.dimension}</p>
            <h4>{insight.currentState}</h4>
            <p>{insight.targetState}</p>
            <strong>{insight.suggestion}</strong>
          </article>
        ))}
      </div>
    </section>
  );
}

function buildJobGapAnalysis(match: MatchResult, resume: ResumeProfile) {
  const missingSkills = uniqueMeaningfulValues(match.missingSkills);
  const matchedSkills = uniqueMeaningfulValues(match.matchedSkills);
  const resumeYears = getResumeYears(resume);
  const experienceMinimum = match.job.experienceRequirements.minTotalYears ?? 0;
  const experienceMaximum = match.job.experienceRequirements.maxTotalYears ?? null;
  const experienceGapYears = Math.max(0, Math.ceil(experienceMinimum - resumeYears));
  const salaryInsight = buildSalaryInsight(match, resume);

  const insights: JobGapInsight[] = [
    buildSkillInsight(missingSkills, matchedSkills),
    buildExperienceInsight(resumeYears, experienceMinimum, experienceMaximum, experienceGapYears),
    salaryInsight.insight,
  ];

  return {
    missingSkills,
    matchedSkills,
    experienceGapYears,
    salaryStatus: salaryInsight.status,
    insights,
  };
}

function buildSkillInsight(missingSkills: string[], matchedSkills: string[]): JobGapInsight {
  if (missingSkills.length === 0) {
    const matchedPreview = matchedSkills.slice(0, 4).join(" / ");
    return {
      dimension: "技能",
      currentState: "核心技能已基本覆盖",
      targetState: matchedPreview ? `已命中 ${matchedPreview}` : "岗位核心技能已基本覆盖",
      suggestion: "把最相关的项目成果和命中技能写得更具体，争取把匹配优势放大。",
    };
  }

  const missingPreview = missingSkills.slice(0, 3).join(" / ");
  return {
    dimension: "技能",
    currentState: `当前仍缺 ${missingSkills.length} 项关键技能`,
    targetState: `优先补齐 ${missingPreview}`,
    suggestion:
      missingSkills.length >= 3
        ? "先补齐最靠前的 2-3 项技能，再把对应项目、实验或实习经历补进简历。"
        : "把缺口技能补到至少一个真实项目里，再更新到技能栈和项目描述中。",
  };
}

function buildExperienceInsight(
  resumeYears: number,
  experienceMinimum: number,
  experienceMaximum: number | null,
  experienceGapYears: number,
): JobGapInsight {
  const targetRange =
    experienceMaximum != null && experienceMaximum >= experienceMinimum
      ? `${experienceMinimum}-${experienceMaximum} 年`
      : `${experienceMinimum} 年以上`;

  if (experienceMinimum <= 0 && experienceMaximum == null) {
    return {
      dimension: "经验",
      currentState: `简历当前标注约 ${resumeYears} 年经验`,
      targetState: "岗位没有明确总年限门槛",
      suggestion: "重点突出最相关的项目复杂度、职责范围和实际产出，而不是只写工作年限。",
    };
  }

  if (experienceGapYears > 0) {
    return {
      dimension: "经验",
      currentState: `当前约 ${resumeYears} 年经验，比岗位下限少 ${experienceGapYears} 年`,
      targetState: `岗位通常需要 ${targetRange}`,
      suggestion: "优先补强和岗位最相关的实习、项目或专项经历，弱化不相关内容，提升说服力。",
    };
  }

  if (experienceMaximum != null && resumeYears > experienceMaximum) {
    return {
      dimension: "经验",
      currentState: `当前约 ${resumeYears} 年经验，已超过岗位常见区间`,
      targetState: `岗位通常面向 ${targetRange}`,
      suggestion: "能力上通常能覆盖该岗位，但要在简历里确认职级预期，避免出现 overqualified 的判断。",
    };
  }

  return {
    dimension: "经验",
    currentState: `当前约 ${resumeYears} 年经验，已达到岗位要求`,
    targetState: `岗位通常需要 ${targetRange}`,
    suggestion: "经验不是主要短板，继续把最贴近岗位场景的经历放在简历前部即可。",
  };
}

function buildSalaryInsight(match: MatchResult, resume: ResumeProfile): {
  status: string;
  insight: JobGapInsight;
} {
  const expectedMin = resume.expectedSalary.min > 0 ? resume.expectedSalary.min : null;
  const expectedMax = resume.expectedSalary.max > 0 ? resume.expectedSalary.max : null;
  const jobMin = match.job.basicInfo.salaryMin ?? match.job.basicInfo.internSalaryAmount ?? null;
  const jobMax = match.job.basicInfo.salaryMax ?? match.job.basicInfo.internSalaryAmount ?? null;

  if (jobMin == null && jobMax == null) {
    return {
      status: "待确认",
      insight: {
        dimension: "薪资",
        currentState: "岗位没有明确薪资区间",
        targetState: "当前无法直接判断谈薪空间",
        suggestion: "如果岗位方向合适，先以技能和职责匹配为主，后续再确认预算范围。",
      },
    };
  }

  if (expectedMin == null && expectedMax == null) {
    return {
      status: "待补充",
      insight: {
        dimension: "薪资",
        currentState: `岗位区间约 ${formatSalaryRange(jobMin, jobMax)}`,
        targetState: "简历中还没有明确期望薪资",
        suggestion: "补充目标薪资后，系统排序和后续谈薪判断都会更准确。",
      },
    };
  }

  if (expectedMin != null && jobMax != null && expectedMin > jobMax) {
    const delta = expectedMin - jobMax;
    return {
      status: "低于期望",
      insight: {
        dimension: "薪资",
        currentState: `你的最低期望比岗位上限高 ${delta} 元/月`,
        targetState: `岗位当前区间约 ${formatSalaryRange(jobMin, jobMax)}`,
        suggestion: "如果你更看重岗位方向，可以适当降低谈薪预期；否则优先投递预算更高的同类岗位。",
      },
    };
  }

  if (expectedMax != null && jobMin != null && expectedMax < jobMin) {
    const delta = jobMin - expectedMax;
    return {
      status: "可上探",
      insight: {
        dimension: "薪资",
        currentState: `岗位下限比当前期望高 ${delta} 元/月`,
        targetState: `岗位通常给到 ${formatSalaryRange(jobMin, jobMax)}`,
        suggestion: "这类岗位预算更好，可以在简历里强化高价值项目，并适度上调你的目标薪资。",
      },
    };
  }

  return {
    status: "基本匹配",
    insight: {
      dimension: "薪资",
      currentState: "期望薪资与岗位区间有重叠",
      targetState: `岗位当前区间约 ${formatSalaryRange(jobMin, jobMax)}`,
      suggestion: "薪资不是主要阻碍，优先把精力放在技能缺口和岗位相关经历的表达上。",
    },
  };
}

function formatSalaryRange(minValue: number | null, maxValue: number | null): string {
  if (minValue != null && maxValue != null) {
    return minValue === maxValue ? `${minValue} 元/月` : `${minValue}-${maxValue} 元/月`;
  }
  if (minValue != null) {
    return `${minValue} 元/月起`;
  }
  if (maxValue != null) {
    return `${maxValue} 元/月以内`;
  }
  return "未注明";
}

function getResumeYears(resume: ResumeProfile): number {
  if (resume.basicInfo.workYears != null && resume.basicInfo.workYears > 0) {
    return resume.basicInfo.workYears;
  }

  const skillYears = resume.skills
    .map((skill: ResumeSkill) => skill.years ?? 0)
    .filter((years) => Number.isFinite(years) && years > 0);
  return skillYears.length > 0 ? Math.max(...skillYears) : 0;
}

function uniqueMeaningfulValues(values: Array<string | null | undefined>): string[] {
  const results: string[] = [];
  const seen = new Set<string>();
  for (const value of values) {
    const normalized = value?.trim();
    if (!normalized) {
      continue;
    }
    const marker = normalized.toLowerCase();
    if (seen.has(marker)) {
      continue;
    }
    seen.add(marker);
    results.push(normalized);
  }
  return results;
}
