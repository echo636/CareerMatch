import type { GapReport, JobProfile, MatchResult, ResumeProfile } from "@/types/domain";

export const mockResumeProfile: ResumeProfile = {
  id: "demo-resume",
  basicInfo: {
    name: "陈晨",
    workYears: 5,
    currentCity: "上海",
    currentTitle: "AI 应用工程师",
    summary: "5 年 Python / 数据产品开发经验，熟悉 LLM 应用、向量检索、Flask 服务设计和岗位匹配场景。",
    selfEvaluation: "具备从结构化解析到匹配评分的完整工程落地经验。",
    firstDegree: "bachelor",
  },
  educations: [
    {
      school: "华东理工大学",
      degree: "bachelor",
      major: "软件工程",
      startYear: "2015",
      endYear: "2019",
    },
  ],
  workExperiences: [
    {
      companyName: "某智能招聘平台",
      title: "后端工程师",
      responsibilities: ["负责简历解析、岗位匹配与评分接口建设"],
      achievements: ["完成结构化入库和召回排序链路搭建"],
      techStack: ["Python", "Flask", "PostgreSQL", "Docker", "LLM"],
    },
  ],
  projects: [
    {
      name: "简历解析",
      role: "核心开发",
      domain: "智能招聘",
      description: "负责多格式简历解析与结构化输出。",
      techStack: ["Python", "LLM", "Embedding"],
    },
    {
      name: "岗位匹配",
      role: "核心开发",
      domain: "推荐系统",
      description: "负责召回、精排和结果解释。",
      techStack: ["Python", "Flask", "PostgreSQL"],
    },
    {
      name: "语义检索",
      role: "方案设计",
      domain: "向量检索",
      description: "负责向量化和召回优化。",
      techStack: ["Embedding", "PostgreSQL", "Docker"],
    },
  ],
  skills: [
    { name: "Python", level: "advanced", years: 5, lastUsedYear: 2026 },
    { name: "Flask", level: "advanced", years: 4, lastUsedYear: 2026 },
    { name: "PostgreSQL", level: "advanced", years: 4, lastUsedYear: 2026 },
    { name: "LLM", level: "advanced", years: 3, lastUsedYear: 2026 },
    { name: "Embedding", level: "intermediate", years: 2, lastUsedYear: 2026 },
    { name: "Prompt Design", level: "intermediate", years: 2, lastUsedYear: 2026 },
    { name: "Docker", level: "intermediate", years: 3, lastUsedYear: 2026 },
  ],
  tags: [
    { name: "Python", category: "tech" },
    { name: "LLM", category: "tech" },
    { name: "简历解析", category: "project" },
    { name: "岗位匹配", category: "project" },
    { name: "智能招聘", category: "domain" },
  ],
  expectedSalary: {
    min: 25000,
    max: 35000,
    currency: "CNY",
  },
  isResume: true,
  sourceFileName: "陈晨_demo_resume.pdf",
  sourceContentType: "application/pdf",
};

export const mockJobs: JobProfile[] = [
  {
    id: "job-001",
    company: "星图智能",
    basicInfo: {
      title: "AI 产品工程师",
      department: "智能招聘平台",
      location: "上海",
      jobType: "fulltime",
      salaryMin: 28000,
      salaryMax: 40000,
      salaryMonthsMin: 14,
      salaryMonthsMax: 16,
      currency: "CNY",
      summary: "负责简历解析、RAG 应用与岗位推荐系统建设，落地 LLM 工作流。",
      responsibilities: ["负责候选人画像、岗位画像与匹配链路设计", "建设向量检索与重排服务"],
      highlights: ["业务核心链路", "可直接影响推荐质量"],
    },
    skillRequirements: {
      required: [
        { name: "Python", level: "advanced", minYears: 3 },
        { name: "LLM", level: "advanced", minYears: 2 },
      ],
      optionalGroups: [
        {
          groupName: "服务框架",
          description: "至少熟悉一种 Python 服务框架",
          minRequired: 1,
          skills: [
            { name: "Flask", level: "advanced" },
            { name: "FastAPI", level: "intermediate" },
          ],
        },
        {
          groupName: "向量检索栈",
          description: "至少具备一种向量检索技术实践",
          minRequired: 1,
          skills: [{ name: "Qdrant" }, { name: "pgvector" }, { name: "Embedding" }],
        },
      ],
      bonus: [
        { name: "PostgreSQL", weight: 6 },
        { name: "Docker", weight: 5 },
      ],
    },
    experienceRequirements: {
      core: [
        { type: "project", name: "简历解析", minYears: 1, keywords: ["简历解析", "结构化"] },
        { type: "project", name: "推荐系统", minYears: 1, keywords: ["岗位匹配", "重排"] },
      ],
      bonus: [{ type: "tech", name: "向量检索", weight: 5, keywords: ["向量检索", "召回优化"] }],
      minTotalYears: 5,
    },
    educationConstraints: {
      minDegree: "bachelor",
      preferredMajors: ["计算机科学", "软件工程"],
    },
    tags: [
      { name: "Python", category: "tech", weight: 5 },
      { name: "LLM", category: "tech", weight: 5 },
      { name: "推荐系统", category: "project", weight: 4 },
      { name: "智能招聘", category: "domain", weight: 5 },
    ],
  },
  {
    id: "job-002",
    company: "知行招聘",
    basicInfo: {
      title: "智能招聘平台后端工程师",
      department: "平台研发",
      location: "杭州",
      jobType: "fulltime",
      salaryMin: 24000,
      salaryMax: 32000,
      salaryMonthsMin: 13,
      salaryMonthsMax: 15,
      currency: "CNY",
      summary: "负责岗位入库、匹配打分与 API 服务，要求具备结构化数据和检索经验。",
      responsibilities: ["设计岗位标准化入库与索引链路", "维护评分服务与接口稳定性"],
      highlights: ["工程链路完整", "强调系统稳定性"],
    },
    skillRequirements: {
      required: [
        { name: "Python", level: "advanced", minYears: 3 },
        { name: "Flask", level: "advanced", minYears: 2 },
      ],
      optionalGroups: [
        {
          groupName: "数据与缓存",
          description: "至少熟悉一种常见数据基础设施",
          minRequired: 1,
          skills: [{ name: "PostgreSQL" }, { name: "Redis" }],
        },
      ],
      bonus: [
        { name: "Docker", weight: 5 },
        { name: "Embedding", weight: 4 },
      ],
    },
    experienceRequirements: {
      core: [
        { type: "project", name: "数据入库", minYears: 1, keywords: ["数据入库", "清洗"] },
        { type: "project", name: "服务编排", minYears: 1, keywords: ["服务编排", "API"] },
      ],
      bonus: [{ type: "tech", name: "匹配评分", weight: 4, keywords: ["匹配评分", "规则引擎"] }],
      minTotalYears: 4,
    },
    educationConstraints: {
      minDegree: "bachelor",
      preferredMajors: ["计算机科学", "信息管理"],
    },
    tags: [
      { name: "Python", category: "tech", weight: 5 },
      { name: "Flask", category: "tech", weight: 5 },
      { name: "数据入库", category: "project", weight: 4 },
      { name: "招聘平台", category: "domain", weight: 4 },
    ],
  },
  {
    id: "job-003",
    company: "零界科技",
    basicInfo: {
      title: "LLM 应用开发工程师",
      department: "Agent 平台",
      location: "深圳",
      jobType: "fulltime",
      salaryMin: 30000,
      salaryMax: 42000,
      salaryMonthsMin: 14,
      salaryMonthsMax: 16,
      currency: "CNY",
      summary: "构建面向求职与人才服务的 AI Agent、Prompt 模板和能力分析模块。",
      responsibilities: ["负责 Agent 工作流和提示词模板", "输出可解释的能力分析与 Gap 报告"],
      highlights: ["Agent 产品方向", "分析与交互并重"],
    },
    skillRequirements: {
      required: [
        { name: "Python", level: "advanced", minYears: 3 },
        { name: "LLM", level: "advanced", minYears: 2 },
      ],
      optionalGroups: [
        {
          groupName: "应用框架",
          description: "至少熟悉一种 AI 应用服务框架",
          minRequired: 1,
          skills: [{ name: "FastAPI" }, { name: "Flask" }],
        },
      ],
      bonus: [
        { name: "Prompt Design", weight: 6 },
        { name: "pgvector", weight: 5 },
      ],
    },
    experienceRequirements: {
      core: [
        { type: "project", name: "Agent", minYears: 1, keywords: ["Agent", "工作流"] },
        { type: "project", name: "Gap 分析", minYears: 1, keywords: ["Gap 分析", "能力建模"] },
      ],
      bonus: [{ type: "tech", name: "提示词工程", weight: 5, keywords: ["提示词工程", "Prompt Design"] }],
      minTotalYears: 6,
    },
    educationConstraints: {
      minDegree: "bachelor",
      preferDegrees: ["master"],
    },
    tags: [
      { name: "LLM", category: "tech", weight: 5 },
      { name: "Prompt Design", category: "tech", weight: 5 },
      { name: "Agent", category: "project", weight: 4 },
      { name: "人才服务", category: "domain", weight: 4 },
    ],
  },
];

export const mockMatches: MatchResult[] = [
  {
    job: mockJobs[0],
    matchedSkills: ["Python", "LLM", "Embedding", "Flask", "PostgreSQL"],
    missingSkills: ["Qdrant", "pgvector", "FastAPI"],
    reasoning: "技能要求命中高、经验要求对齐高，当前已命中 Python / LLM / Embedding，主要待补齐 Qdrant / pgvector。",
    breakdown: {
      vectorSimilarity: 0.92,
      skillMatch: 0.89,
      experienceMatch: 0.87,
      educationMatch: 0.94,
      salaryMatch: 0.9,
      total: 0.897,
    },
  },
  {
    job: mockJobs[1],
    matchedSkills: ["Python", "Flask", "PostgreSQL", "Docker", "Embedding"],
    missingSkills: ["Redis"],
    reasoning: "技能要求命中高，当前已命中 Python / Flask / PostgreSQL，主要待补齐 Redis。",
    breakdown: {
      vectorSimilarity: 0.84,
      skillMatch: 0.82,
      experienceMatch: 0.56,
      educationMatch: 0.88,
      salaryMatch: 0.96,
      total: 0.779,
    },
  },
  {
    job: mockJobs[2],
    matchedSkills: ["Python", "LLM", "Prompt Design", "Flask"],
    missingSkills: ["FastAPI", "pgvector"],
    reasoning: "结构化条件整体较匹配，当前已命中 Python / LLM / Prompt Design，主要待补齐 FastAPI / pgvector。",
    breakdown: {
      vectorSimilarity: 0.81,
      skillMatch: 0.74,
      experienceMatch: 0.49,
      educationMatch: 0.76,
      salaryMatch: 0.84,
      total: 0.704,
    },
  },
];

export const mockGapReport: GapReport = {
  baselineRoles: mockMatches.slice(0, 2).map((match) => match.job.basicInfo.title),
  missingSkills: ["Qdrant", "Redis", "FastAPI"],
  salaryGap: 4000,
  experienceGapYears: 1,
  insights: [
    {
      dimension: "技能",
      currentState: "已具备 Python、Flask、LLM 与数据建模能力。",
      targetState: "补齐 Qdrant / pgvector 与缓存层实践，形成完整检索栈能力。",
      suggestion: "以岗位匹配场景补一个向量检索 + 缓存降本的项目案例。",
    },
    {
      dimension: "经验",
      currentState: "具备单体服务和 AI 工作流集成经验。",
      targetState: "增强面向批量岗位入库与异步任务调度的落地案例。",
      suggestion: "在项目骨架中继续补齐队列、回放和批处理链路。",
    },
    {
      dimension: "薪资",
      currentState: "当前期望区间与中高匹配岗位接近。",
      targetState: "通过向量库和推荐系统实绩支撑更高薪资带。",
      suggestion: "优先沉淀可量化的召回率、匹配准确率指标。",
    },
  ],
};
