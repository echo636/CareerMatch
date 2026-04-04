import type { GapReport, MatchFilters, MatchResult, ResumeProfile } from "@/types/domain";

import { logFrontendEvent, summarizeFrontendPayload } from "@/lib/logger";
import { normalizeMatchFilters } from "@/lib/match-filters";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL;

type UploadResumeResponse = {
  resume: ResumeProfile;
  resumeId: string;
};

const emptyGapReport: GapReport = {
  baselineRoles: [],
  missingSkills: [],
  salaryGap: 0,
  experienceGapYears: 0,
  insights: [],
};

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  if (!API_BASE_URL) {
    const message = "NEXT_PUBLIC_API_BASE_URL is not configured.";
    logFrontendEvent("api.request.skipped", { path, reason: message }, "warn");
    throw new Error(message);
  }

  const method = init?.method ?? "GET";
  const startedAt = Date.now();
  logFrontendEvent("api.request.start", {
    method,
    path,
    hasBody: Boolean(init?.body),
  });

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
    cache: "no-store",
  });

  if (!response.ok) {
    const message = await getErrorMessage(response);
    logFrontendEvent(
      "api.request.error",
      {
        method,
        path,
        status: response.status,
        durationMs: Date.now() - startedAt,
        message,
      },
      "error",
    );
    throw new Error(message);
  }

  const payload = (await response.json()) as T;
  logFrontendEvent("api.request.success", {
    method,
    path,
    status: response.status,
    durationMs: Date.now() - startedAt,
    response: summarizeFrontendPayload(payload),
  });
  return payload;
}

async function getErrorMessage(response: Response): Promise<string> {
  try {
    const payload = (await response.json()) as { error?: string };
    return payload.error ?? `API request failed: ${response.status}`;
  } catch {
    return `API request failed: ${response.status}`;
  }
}

export async function uploadResume(formData: FormData): Promise<UploadResumeResponse> {
  if (!API_BASE_URL) {
    const message = "NEXT_PUBLIC_API_BASE_URL is not configured. Start the backend and set frontend/.env.local.";
    logFrontendEvent("resume.upload.skipped", { reason: message }, "warn");
    throw new Error(message);
  }

  const content = String(formData.get("content") ?? "").trim();
  const file = formData.get("file");
  const startedAt = Date.now();
  logFrontendEvent("resume.upload.request.start", {
    path: "/resumes/upload",
    hasTextContent: content.length > 0,
    contentLength: content.length,
    fileName: file instanceof File ? file.name : null,
    fileSize: file instanceof File ? file.size : null,
  });

  const response = await fetch(`${API_BASE_URL}/resumes/upload`, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    const message = await getErrorMessage(response);
    logFrontendEvent(
      "resume.upload.request.error",
      {
        path: "/resumes/upload",
        status: response.status,
        durationMs: Date.now() - startedAt,
        message,
      },
      "error",
    );
    throw new Error(message);
  }

  const payload = (await response.json()) as UploadResumeResponse;
  logFrontendEvent("resume.upload.request.success", {
    path: "/resumes/upload",
    status: response.status,
    durationMs: Date.now() - startedAt,
    response: summarizeFrontendPayload(payload),
  });
  return payload;
}

export async function getResumePreview(resumeId?: string | null): Promise<ResumeProfile | null> {
  const normalizedResumeId = resumeId?.trim();
  if (!normalizedResumeId || !API_BASE_URL) {
    logFrontendEvent(
      "resume.preview.skipped",
      {
        resumeId: normalizedResumeId ?? null,
        hasApiBaseUrl: Boolean(API_BASE_URL),
      },
      "warn",
    );
    return null;
  }

  try {
    const response = await request<{ resume: ResumeProfile }>(`/resumes/${normalizedResumeId}`);
    return response.resume;
  } catch (error) {
    logFrontendEvent(
      "resume.preview.failed",
      {
        resumeId: normalizedResumeId,
        message: error instanceof Error ? error.message : "unknown_error",
      },
      "warn",
    );
    return null;
  }
}

export async function getMatchOverview(
  resumeId?: string | null,
  topK: number = 3,
  filters?: MatchFilters,
): Promise<MatchResult[]> {
  const normalizedResumeId = resumeId?.trim();
  if (!normalizedResumeId || !API_BASE_URL) {
    logFrontendEvent(
      "matches.overview.skipped",
      {
        resumeId: normalizedResumeId ?? null,
        hasApiBaseUrl: Boolean(API_BASE_URL),
      },
      "warn",
    );
    return [];
  }

  try {
    const response = await request<{ matches: MatchResult[] }>("/matches/recommend", {
      method: "POST",
      body: JSON.stringify({
        resume_id: normalizedResumeId,
        top_k: topK,
        filters: filters ? normalizeMatchFilters(filters) : undefined,
      }),
    });
    return response.matches;
  } catch (error) {
    logFrontendEvent(
      "matches.overview.failed",
      {
        resumeId: normalizedResumeId,
        message: error instanceof Error ? error.message : "unknown_error",
      },
      "warn",
    );
    return [];
  }
}

export async function getGapReport(resumeId?: string | null, filters?: MatchFilters): Promise<GapReport> {
  const normalizedResumeId = resumeId?.trim();
  if (!normalizedResumeId || !API_BASE_URL) {
    logFrontendEvent(
      "gap.report.skipped",
      {
        resumeId: normalizedResumeId ?? null,
        hasApiBaseUrl: Boolean(API_BASE_URL),
      },
      "warn",
    );
    return emptyGapReport;
  }

  try {
    const response = await request<{ report: GapReport }>("/gap/report", {
      method: "POST",
      body: JSON.stringify({
        resume_id: normalizedResumeId,
        top_k: 3,
        filters: filters ? normalizeMatchFilters(filters) : undefined,
      }),
    });
    return response.report;
  } catch (error) {
    logFrontendEvent(
      "gap.report.failed",
      {
        resumeId: normalizedResumeId,
        message: error instanceof Error ? error.message : "unknown_error",
      },
      "warn",
    );
    return emptyGapReport;
  }
}
