export type SalaryRange = {
  min: number;
  max: number;
  currency: string;
};

export type ResumeProfile = {
  id: string;
  candidateName: string;
  summary: string;
  skills: string[];
  projectKeywords: string[];
  yearsExperience: number;
  expectedSalary: SalaryRange;
  rawText?: string;
  sourceFileName?: string;
  sourceContentType?: string;
  sourceObjectKey?: string;
};

export type JobProfile = {
  id: string;
  title: string;
  company: string;
  location: string;
  summary: string;
  skills: string[];
  projectKeywords: string[];
  hardRequirements: string[];
  salaryRange: SalaryRange;
};

export type MatchBreakdown = {
  vectorSimilarity: number;
  skillMatch: number;
  projectMatch: number;
  salaryMatch: number;
  total: number;
};

export type MatchResult = {
  job: JobProfile;
  breakdown: MatchBreakdown;
  matchedSkills: string[];
  missingSkills: string[];
  reasoning: string;
};

export type GapInsight = {
  dimension: string;
  currentState: string;
  targetState: string;
  suggestion: string;
};

export type GapReport = {
  baselineRoles: string[];
  missingSkills: string[];
  salaryGap: number;
  experienceGapYears: number;
  insights: GapInsight[];
};