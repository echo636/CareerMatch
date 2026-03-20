import { mockGapReport, mockJobs, mockMatches, mockResumeProfile } from "@/lib/mock-data";
import type { GapReport, JobProfile, MatchResult, ResumeProfile } from "@/types/domain";

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

function cloneMockResume(resumeId: string): ResumeProfile {
  return {
    ...mockResumeProfile,
    id: resumeId,
  };
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

export async function getResumePreview(resumeId = "demo-resume"): Promise<ResumeProfile> {
  if (!API_BASE_URL) {
    return resumeId === "demo-resume" ? mockResumeProfile : cloneMockResume(resumeId);
  }

  try {
    const path = resumeId === "demo-resume" ? "/resumes/demo" : `/resumes/${resumeId}`;
    const response = await request<{ resume: ResumeProfile }>(path);
    return response.resume;
  } catch {
    return resumeId === "demo-resume" ? mockResumeProfile : cloneMockResume(resumeId);
  }
}

export async function getJobsPreview(): Promise<JobProfile[]> {
  if (!API_BASE_URL) {
    return mockJobs;
  }

  try {
    const response = await request<{ jobs: JobProfile[] }>("/jobs");
    return response.jobs;
  } catch {
    return mockJobs;
  }
}

export async function getMatchOverview(resumeId = "demo-resume"): Promise<MatchResult[]> {
  if (!API_BASE_URL) {
    return resumeId === "demo-resume" ? mockMatches : [];
  }

  try {
    const response = await request<{ matches: MatchResult[] }>("/matches/recommend", {
      method: "POST",
      body: JSON.stringify({
        resume_id: resumeId,
        top_k: 3,
      }),
    });
    return response.matches;
  } catch {
    return resumeId === "demo-resume" ? mockMatches : [];
  }
}

export async function getGapReport(resumeId = "demo-resume"): Promise<GapReport> {
  if (!API_BASE_URL) {
    return resumeId === "demo-resume" ? mockGapReport : emptyGapReport;
  }

  try {
    const response = await request<{ report: GapReport }>("/gap/report", {
      method: "POST",
      body: JSON.stringify({
        resume_id: resumeId,
        top_k: 3,
      }),
    });
    return response.report;
  } catch {
    return resumeId === "demo-resume" ? mockGapReport : emptyGapReport;
  }
}