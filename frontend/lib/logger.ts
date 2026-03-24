export type FrontendLogLevel = "info" | "warn" | "error";

const PREFIX = "[CareerMatch FE]";

export function logFrontendEvent(
  event: string,
  payload?: Record<string, unknown> | unknown,
  level: FrontendLogLevel = "info",
): void {
  const line = `${PREFIX} ${new Date().toISOString()} ${event}`;
  const printer = level === "error" ? console.error : level === "warn" ? console.warn : console.info;
  if (payload === undefined) {
    printer(line);
    return;
  }
  printer(line, payload);
}

export function summarizeFrontendPayload(payload: unknown): Record<string, unknown> | unknown {
  if (payload === null || payload === undefined) {
    return payload;
  }
  if (Array.isArray(payload)) {
    return { type: "array", length: payload.length };
  }
  if (typeof payload !== "object") {
    return payload;
  }

  const record = payload as Record<string, unknown>;
  const summary: Record<string, unknown> = {
    keys: Object.keys(record),
  };

  if (typeof record.resumeId === "string") {
    summary.resumeId = record.resumeId;
  }
  if (record.resume && typeof record.resume === "object") {
    const resume = record.resume as Record<string, unknown>;
    summary.resume = {
      id: resume.id,
      sourceFileName: resume.sourceFileName,
      skillCount: Array.isArray(resume.skills) ? resume.skills.length : undefined,
      projectCount: Array.isArray(resume.projects) ? resume.projects.length : undefined,
    };
  }
  if (Array.isArray(record.matches)) {
    summary.matches = {
      count: record.matches.length,
    };
  }
  if (record.report && typeof record.report === "object") {
    const report = record.report as Record<string, unknown>;
    summary.report = {
      baselineRoleCount: Array.isArray(report.baselineRoles) ? report.baselineRoles.length : undefined,
      missingSkillCount: Array.isArray(report.missingSkills) ? report.missingSkills.length : undefined,
      insightCount: Array.isArray(report.insights) ? report.insights.length : undefined,
    };
  }

  return summary;
}
