import type { MatchFilters, WorkMode } from "@/types/domain";

export const ROLE_CATEGORY_OPTIONS = [
  { value: "hardware_engineer", label: "硬件工程师" },
  { value: "embedded_engineer", label: "嵌入式工程师" },
  { value: "frontend_engineer", label: "前端工程师" },
  { value: "backend_engineer", label: "后端工程师" },
  { value: "fullstack_engineer", label: "全栈工程师" },
  { value: "testing_engineer", label: "测试工程师" },
  { value: "algorithm_engineer", label: "算法工程师" },
  { value: "data_engineer", label: "数据工程师" },
  { value: "devops_engineer", label: "DevOps / SRE" },
  { value: "mobile_engineer", label: "移动端工程师" },
  { value: "product_manager", label: "产品经理" },
  { value: "uiux_designer", label: "UI / UX 设计师" },
] as const;

export const WORK_MODE_OPTIONS: Array<{ value: WorkMode; label: string }> = [
  { value: "remote", label: "远程" },
  { value: "hybrid", label: "混合办公" },
  { value: "onsite", label: "现场 / 坐班" },
];

export const INTERNSHIP_OPTIONS = [
  { value: "all", label: "不限" },
  { value: "intern", label: "仅实习" },
  { value: "fulltime", label: "仅非实习" },
] as const;

export const POST_TIME_OPTIONS = [
  { value: "", label: "不限" },
  { value: "3", label: "近 3 天" },
  { value: "7", label: "近 7 天" },
  { value: "30", label: "近 30 天" },
  { value: "90", label: "近 90 天" },
] as const;

export const EXPERIENCE_YEAR_OPTIONS = [
  { value: "", label: "不限" },
  { value: "0", label: "0 年" },
  { value: "1", label: "1 年" },
  { value: "3", label: "3 年" },
  { value: "5", label: "5 年" },
  { value: "8", label: "8 年" },
  { value: "10", label: "10 年+" },
] as const;

export const DEFAULT_MATCH_FILTERS: MatchFilters = {
  roleCategories: [],
  workModes: [],
  internshipPreference: "all",
  postedWithinDays: null,
  minExperienceYears: null,
  maxExperienceYears: null,
};

export function normalizeMatchFilters(filters: MatchFilters): MatchFilters {
  return {
    roleCategories: deduplicateStrings(filters.roleCategories),
    workModes: deduplicateStrings(filters.workModes) as WorkMode[],
    internshipPreference: filters.internshipPreference,
    postedWithinDays: normalizePositiveNumber(filters.postedWithinDays),
    minExperienceYears: normalizeNonNegativeNumber(filters.minExperienceYears),
    maxExperienceYears: normalizeNonNegativeNumber(filters.maxExperienceYears),
  };
}

export function hasActiveMatchFilters(filters: MatchFilters): boolean {
  const normalized = normalizeMatchFilters(filters);
  return Boolean(
    normalized.roleCategories.length > 0 ||
      normalized.workModes.length > 0 ||
      normalized.internshipPreference !== "all" ||
      normalized.postedWithinDays != null ||
      normalized.minExperienceYears != null ||
      normalized.maxExperienceYears != null,
  );
}

export function parseMatchFiltersFromSearchParams(
  searchParams: Record<string, string | string[] | undefined>,
): MatchFilters {
  const roleCategories = parseCsvParam(searchParams.roles);
  const workModes = parseCsvParam(searchParams.workModes) as WorkMode[];
  const internshipPreference = normalizeInternshipPreference(searchParams.internship);

  return normalizeMatchFilters({
    roleCategories,
    workModes,
    internshipPreference,
    postedWithinDays: parseNumberParam(searchParams.postedWithinDays),
    minExperienceYears: parseNumberParam(searchParams.minExp),
    maxExperienceYears: parseNumberParam(searchParams.maxExp),
  });
}

export function appendMatchFiltersToSearchParams(
  params: URLSearchParams,
  filters: MatchFilters,
): URLSearchParams {
  const normalized = normalizeMatchFilters(filters);
  params.delete("roles");
  params.delete("workModes");
  params.delete("internship");
  params.delete("postedWithinDays");
  params.delete("minExp");
  params.delete("maxExp");

  if (normalized.roleCategories.length > 0) {
    params.set("roles", normalized.roleCategories.join(","));
  }
  if (normalized.workModes.length > 0) {
    params.set("workModes", normalized.workModes.join(","));
  }
  if (normalized.internshipPreference !== "all") {
    params.set("internship", normalized.internshipPreference);
  }
  if (normalized.postedWithinDays != null) {
    params.set("postedWithinDays", String(normalized.postedWithinDays));
  }
  if (normalized.minExperienceYears != null) {
    params.set("minExp", String(normalized.minExperienceYears));
  }
  if (normalized.maxExperienceYears != null) {
    params.set("maxExp", String(normalized.maxExperienceYears));
  }
  return params;
}

export function getMatchFilterSummary(filters: MatchFilters): string[] {
  const normalized = normalizeMatchFilters(filters);
  const summaries: string[] = [];

  for (const roleCategory of normalized.roleCategories) {
    const option = ROLE_CATEGORY_OPTIONS.find((item) => item.value === roleCategory);
    summaries.push(option?.label ?? roleCategory);
  }

  if (normalized.internshipPreference === "intern") {
    summaries.push("仅实习");
  } else if (normalized.internshipPreference === "fulltime") {
    summaries.push("仅非实习");
  }

  for (const workMode of normalized.workModes) {
    const option = WORK_MODE_OPTIONS.find((item) => item.value === workMode);
    summaries.push(option?.label ?? workMode);
  }

  if (normalized.postedWithinDays != null) {
    summaries.push(`发布时间 ${normalized.postedWithinDays} 天内`);
  }
  if (normalized.minExperienceYears != null || normalized.maxExperienceYears != null) {
    const left = normalized.minExperienceYears ?? 0;
    const right = normalized.maxExperienceYears;
    summaries.push(right != null ? `经验要求 ${left}-${right} 年` : `经验要求 ${left} 年以上`);
  }

  return summaries;
}

function parseCsvParam(value: string | string[] | undefined): string[] {
  const normalized = Array.isArray(value) ? value[0] : value;
  if (!normalized) {
    return [];
  }
  return deduplicateStrings(normalized.split(","));
}

function parseNumberParam(value: string | string[] | undefined): number | null {
  const normalized = Array.isArray(value) ? value[0] : value;
  if (!normalized) {
    return null;
  }
  const parsed = Number.parseFloat(normalized);
  return Number.isFinite(parsed) ? parsed : null;
}

function deduplicateStrings(values: readonly string[]): string[] {
  const results: string[] = [];
  const seen = new Set<string>();
  for (const value of values) {
    const normalized = String(value ?? "").trim().toLowerCase();
    if (!normalized || seen.has(normalized)) {
      continue;
    }
    seen.add(normalized);
    results.push(normalized);
  }
  return results;
}

function normalizeInternshipPreference(value: string | string[] | undefined): MatchFilters["internshipPreference"] {
  const normalized = (Array.isArray(value) ? value[0] : value)?.trim().toLowerCase();
  if (normalized === "intern" || normalized === "fulltime") {
    return normalized;
  }
  return "all";
}

function normalizePositiveNumber(value: number | null | undefined): number | null {
  return typeof value === "number" && Number.isFinite(value) && value > 0 ? value : null;
}

function normalizeNonNegativeNumber(value: number | null | undefined): number | null {
  return typeof value === "number" && Number.isFinite(value) && value >= 0 ? value : null;
}
