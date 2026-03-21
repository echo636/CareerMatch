export type SalaryRange = {
  min: number;
  max: number;
  currency: string;
};

export type ResumeBasicInfo = {
  name: string;
  gender?: string | null;
  age?: number | null;
  workYears?: number | null;
  currentCity?: string | null;
  currentTitle?: string | null;
  currentCompany?: string | null;
  status?: string | null;
  email?: string | null;
  phone?: string | null;
  wechat?: string | null;
  ethnicity?: string | null;
  birthDate?: string | null;
  nativePlace?: string | null;
  residence?: string | null;
  politicalStatus?: string | null;
  idNumber?: string | null;
  maritalStatus?: string | null;
  summary?: string | null;
  selfEvaluation?: string | null;
  firstDegree?: string | null;
  avatar?: string | null;
};

export type ResumeEducation = {
  school: string;
  degree?: string | null;
  major?: string | null;
  startYear?: string | null;
  endYear?: string | null;
};

export type ResumeWorkExperience = {
  companyName: string;
  industry?: string | null;
  title: string;
  level?: string | null;
  location?: string | null;
  startDate?: string | null;
  endDate?: string | null;
  responsibilities?: string[];
  achievements?: string[];
  techStack?: string[];
};

export type ResumeProject = {
  name: string;
  role?: string | null;
  domain?: string | null;
  description?: string | null;
  responsibilities?: string[];
  achievements?: string[];
  techStack?: string[];
};

export type ResumeSkill = {
  name: string;
  level?: string | null;
  years?: number | null;
  lastUsedYear?: number | null;
};

export type ResumeTag = {
  name: string;
  category?: string | null;
};

export type ResumeProfile = {
  id: string;
  basicInfo: ResumeBasicInfo;
  educations: ResumeEducation[];
  workExperiences: ResumeWorkExperience[];
  projects: ResumeProject[];
  skills: ResumeSkill[];
  tags: ResumeTag[];
  expectedSalary: SalaryRange;
  isResume?: boolean | null;
  rawText?: string;
  sourceFileName?: string;
  sourceContentType?: string;
  sourceObjectKey?: string;
};

export type JobBasicInfo = {
  title: string;
  department?: string | null;
  location?: string | null;
  jobType?: string | null;
  salaryNegotiable?: boolean | null;
  salaryMin?: number | null;
  salaryMax?: number | null;
  salaryMonthsMin?: number | null;
  salaryMonthsMax?: number | null;
  internSalaryAmount?: number | null;
  internSalaryUnit?: string | null;
  currency?: string | null;
  summary?: string | null;
  responsibilities?: string[];
  highlights?: string[];
};

export type RequiredSkill = {
  name: string;
  level?: string | null;
  minYears?: number | null;
  description?: string | null;
};

export type OptionalSkill = {
  name: string;
  level?: string | null;
  description?: string | null;
};

export type OptionalSkillGroup = {
  groupName: string;
  description?: string | null;
  minRequired: number;
  skills: OptionalSkill[];
};

export type BonusSkill = {
  name: string;
  weight?: number | null;
  description?: string | null;
};

export type JobSkillRequirements = {
  required: RequiredSkill[];
  optionalGroups: OptionalSkillGroup[];
  bonus: BonusSkill[];
};

export type CoreExperience = {
  type: string;
  name: string;
  minYears?: number | null;
  description?: string | null;
  keywords?: string[];
};

export type BonusExperience = {
  type: string;
  name: string;
  weight?: number | null;
  description?: string | null;
  keywords?: string[];
};

export type JobExperienceRequirements = {
  core: CoreExperience[];
  bonus: BonusExperience[];
  minTotalYears?: number | null;
  maxTotalYears?: number | null;
};

export type LanguageRequirement = {
  language: string;
  level?: string | null;
  required: boolean;
};

export type JobEducationConstraints = {
  minDegree?: string | null;
  preferDegrees?: string[];
  requiredMajors?: string[];
  preferredMajors?: string[];
  languages?: LanguageRequirement[];
  certifications?: string[];
  ageRange?: string | null;
  other?: string[];
};

export type JobTag = {
  name: string;
  category?: string | null;
  weight?: number | null;
};

export type JobProfile = {
  id: string;
  company: string;
  basicInfo: JobBasicInfo;
  skillRequirements: JobSkillRequirements;
  experienceRequirements: JobExperienceRequirements;
  educationConstraints: JobEducationConstraints;
  tags: JobTag[];
};

export type MatchBreakdown = {
  vectorSimilarity: number;
  skillMatch: number;
  experienceMatch: number;
  educationMatch: number;
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
