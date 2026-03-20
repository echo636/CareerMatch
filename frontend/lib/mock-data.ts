import type { GapReport, JobProfile, MatchResult, ResumeProfile } from "@/types/domain";

export const mockResumeProfile: ResumeProfile = {
  id: "demo-resume",
  candidateName: "陈晨",
  summary:
    "5 年 Python / 数据产品开发经验，熟悉 LLM 应用、向量检索、Flask 服务设计和岗位匹配场景。",
  skills: ["Python", "Flask", "PostgreSQL", "LLM", "Embedding", "Prompt Design", "Docker"],
  projectKeywords: ["简历解析", "岗位匹配", "语义检索", "评分系统"],
  yearsExperience: 5,
  expectedSalary: {
    min: 25000,
    max: 35000,
    currency: "CNY",
  },
  sourceFileName: "陈晨_demo_resume.pdf",
  sourceContentType: "application/pdf",
};

export const mockJobs: JobProfile[] = [
  {
    id: "job-001",
    title: "AI 产品工程师",
    company: "星图智能",
    location: "上海",
    summary: "负责简历解析、RAG 应用与岗位推荐系统建设，落地 LLM 工作流。",
    skills: ["Python", "LLM", "Embedding", "Flask", "Qdrant", "PostgreSQL"],
    projectKeywords: ["简历解析", "向量检索", "推荐系统"],
    hardRequirements: ["Python", "LLM"],
    salaryRange: {
      min: 28000,
      max: 40000,
      currency: "CNY",
    },
  },
  {
    id: "job-002",
    title: "智能招聘平台后端工程师",
    company: "知行招聘",
    location: "杭州",
    summary: "负责岗位入库、匹配打分与 API 服务，要求具备结构化数据和检索经验。",
    skills: ["Python", "Flask", "PostgreSQL", "Docker", "Redis"],
    projectKeywords: ["数据入库", "匹配评分", "服务编排"],
    hardRequirements: ["Python", "Flask"],
    salaryRange: {
      min: 24000,
      max: 32000,
      currency: "CNY",
    },
  },
  {
    id: "job-003",
    title: "LLM 应用开发工程师",
    company: "零界科技",
    location: "深圳",
    summary: "构建面向求职与人才服务的 AI Agent、Prompt 模板和能力分析模块。",
    skills: ["Python", "LLM", "Prompt Design", "FastAPI", "pgvector"],
    projectKeywords: ["Agent", "Gap 分析", "提示词工程"],
    hardRequirements: ["Python", "LLM"],
    salaryRange: {
      min: 30000,
      max: 42000,
      currency: "CNY",
    },
  },
];

export const mockMatches: MatchResult[] = [
  {
    job: mockJobs[0],
    matchedSkills: ["Python", "LLM", "Embedding", "Flask", "PostgreSQL"],
    missingSkills: ["Qdrant"],
    reasoning: "简历与岗位在 AI 解析、向量检索和服务接口设计上高度重合，缺口主要在专门的向量库实践。",
    breakdown: {
      vectorSimilarity: 0.92,
      skillMatch: 0.83,
      projectMatch: 0.88,
      salaryMatch: 0.9,
      total: 0.88,
    },
  },
  {
    job: mockJobs[1],
    matchedSkills: ["Python", "Flask", "PostgreSQL", "Docker"],
    missingSkills: ["Redis"],
    reasoning: "后端基础能力匹配充分，岗位对入库和调度流程的要求与 README 设定一致。",
    breakdown: {
      vectorSimilarity: 0.84,
      skillMatch: 0.8,
      projectMatch: 0.77,
      salaryMatch: 0.96,
      total: 0.83,
    },
  },
  {
    job: mockJobs[2],
    matchedSkills: ["Python", "LLM", "Prompt Design"],
    missingSkills: ["FastAPI", "pgvector"],
    reasoning: "候选人在 LLM 应用层有较强积累，但与岗位在框架和向量存储选型上仍有补足空间。",
    breakdown: {
      vectorSimilarity: 0.81,
      skillMatch: 0.61,
      projectMatch: 0.75,
      salaryMatch: 0.84,
      total: 0.74,
    },
  },
];

export const mockGapReport: GapReport = {
  baselineRoles: mockMatches.slice(0, 2).map((match) => match.job.title),
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