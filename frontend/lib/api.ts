import type { GapReport, MatchResult, ResumeProfile } from "@/types/domain";

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
    throw new Error("NEXT_PUBLIC_API_BASE_URL is not configured.");
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error(await getErrorMessage(response));
  }

  return (await response.json()) as T;
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
    throw new Error("NEXT_PUBLIC_API_BASE_URL is not configured. Start the backend and set frontend/.env.local.");
  }

  const response = await fetch(`${API_BASE_URL}/resumes/upload`, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    throw new Error(await getErrorMessage(response));
  }

  return (await response.json()) as UploadResumeResponse;
}

export async function getResumePreview(resumeId?: string | null): Promise<ResumeProfile | null> {
  const normalizedResumeId = resumeId?.trim();
  if (!normalizedResumeId || !API_BASE_URL) {
    return null;
  }

  try {
    const response = await request<{ resume: ResumeProfile }>(`/resumes/${normalizedResumeId}`);
    return response.resume;
  } catch {
    return null;
  }
}

export async function getMatchOverview(resumeId?: string | null): Promise<MatchResult[]> {
  const normalizedResumeId = resumeId?.trim();
  if (!normalizedResumeId || !API_BASE_URL) {
    return [];
  }

  try {
    const response = await request<{ matches: MatchResult[] }>("/matches/recommend", {
      method: "POST",
      body: JSON.stringify({
        resume_id: normalizedResumeId,
        top_k: 3,
      }),
    });
    return response.matches;
  } catch {
    return [];
  }
}

export async function getGapReport(resumeId?: string | null): Promise<GapReport> {
  const normalizedResumeId = resumeId?.trim();
  if (!normalizedResumeId || !API_BASE_URL) {
    return emptyGapReport;
  }

  try {
    const response = await request<{ report: GapReport }>("/gap/report", {
      method: "POST",
      body: JSON.stringify({
        resume_id: normalizedResumeId,
        top_k: 3,
      }),
    });
    return response.report;
  } catch {
    return emptyGapReport;
  }
}
