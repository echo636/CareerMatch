"use client";

import type { ChangeEvent, FormEvent } from "react";
import { useState } from "react";
import { useRouter } from "next/navigation";
import type { Route } from "next";

import { MatchFilterForm } from "@/components/matches/match-filter-form";
import { appendMatchFiltersToSearchParams, DEFAULT_MATCH_FILTERS } from "@/lib/match-filters";
import { uploadResume } from "@/lib/api";
import { logFrontendEvent } from "@/lib/logger";
import type { MatchFilters } from "@/types/domain";

export function ResumeUploadForm() {
  const router = useRouter();
  const [selectedFileName, setSelectedFileName] = useState("未选择文件");
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [pendingResumeId, setPendingResumeId] = useState<string | null>(null);
  const [isFilterModalOpen, setIsFilterModalOpen] = useState(false);
  const [isRedirecting, setIsRedirecting] = useState(false);

  function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
    const nextFile = event.target.files?.[0];
    setSelectedFileName(nextFile?.name ?? "未选择文件");
    logFrontendEvent("resume.form.file_selected", {
      fileName: nextFile?.name ?? null,
      fileSize: nextFile?.size ?? null,
      fileType: nextFile?.type ?? null,
    });
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setStatus(null);

    const form = event.currentTarget;
    const formData = new FormData(form);
    const content = String(formData.get("content") ?? "").trim();
    const file = formData.get("file");
    const hasFile = file instanceof File && file.size > 0;

    logFrontendEvent("resume.form.submit_clicked", {
      hasTextContent: content.length > 0,
      contentLength: content.length,
      hasFile,
      fileName: file instanceof File ? file.name : null,
    });

    if (!content && !hasFile) {
      const message = "请粘贴简历文本，或上传一份 PDF、DOCX、TXT、MD 文件。";
      setError(message);
      logFrontendEvent("resume.form.submit_blocked", { reason: "missing_content_and_file" }, "warn");
      return;
    }

    setIsSubmitting(true);
    setStatus("正在解析简历，请稍候...");
    logFrontendEvent("resume.form.submit_started");

    try {
      const payload = await uploadResume(formData);
      setPendingResumeId(payload.resumeId);
      setStatus("简历解析完成，请先设置岗位筛选条件，再开始匹配。");
      setIsFilterModalOpen(true);
      logFrontendEvent("resume.form.submit_succeeded", {
        resumeId: payload.resumeId,
        sourceFileName: payload.resume.sourceFileName ?? null,
      });
    } catch (submitError) {
      const message = submitError instanceof Error ? submitError.message : "上传失败，请稍后重试。";
      setStatus(null);
      setError(message);
      logFrontendEvent("resume.form.submit_failed", { message }, "error");
    } finally {
      setIsSubmitting(false);
    }
  }

  function handleStartMatching(filters: MatchFilters) {
    if (!pendingResumeId) {
      return;
    }
    setIsRedirecting(true);
    setError(null);
    setStatus("正在跳转到匹配结果...");
    setIsFilterModalOpen(false);

    const params = new URLSearchParams();
    params.set("resumeId", pendingResumeId);
    appendMatchFiltersToSearchParams(params, filters);
    const target = `/matches?${params.toString()}` as Route;

    logFrontendEvent("resume.form.redirecting", {
      target: "/matches",
      resumeId: pendingResumeId,
      filters,
    });
    router.push(target);
    router.refresh();
  }

  function handleViewAllMatches() {
    handleStartMatching(DEFAULT_MATCH_FILTERS);
  }

  return (
    <>
      <form className="form-stack" onSubmit={handleSubmit}>
        <div className="field-group">
          <label className="field-label" htmlFor="resume-content">
            简历文本
          </label>
          <textarea
            id="resume-content"
            name="content"
            className="field-textarea"
            placeholder="可直接粘贴简历正文；如果同时上传文件，这里的文本会优先作为解析内容。"
            rows={12}
          />
          <p className="field-help">支持 PDF、DOCX、TXT、MD。旧版 .doc 暂不支持。</p>
        </div>

        <div className="field-group">
          <label className="field-label" htmlFor="resume-file">
            简历文件
          </label>
          <input
            id="resume-file"
            name="file"
            type="file"
            className="field-input"
            accept=".txt,.md,.pdf,.docx"
            onChange={handleFileChange}
          />
          <p className="upload-meta">当前文件：{selectedFileName}</p>
        </div>

        {status ? <p className="status-message">{status}</p> : null}
        {error ? <p className="status-message status-error">{error}</p> : null}

        <div className="button-row">
          <button type="submit" className="button-primary" disabled={isSubmitting || isRedirecting}>
            {isSubmitting ? "正在处理中..." : "上传并设置匹配条件"}
          </button>
          {pendingResumeId ? (
            <button
              type="button"
              className="button-secondary"
              onClick={() => setIsFilterModalOpen(true)}
              disabled={isRedirecting}
            >
              继续设置筛选
            </button>
          ) : null}
          {pendingResumeId ? (
            <button type="button" className="button-ghost" onClick={handleViewAllMatches} disabled={isRedirecting}>
              直接查看全部结果
            </button>
          ) : null}
        </div>
      </form>

      {isFilterModalOpen ? (
        <div className="modal-overlay" role="dialog" aria-modal="true" aria-labelledby="match-filter-title">
          <div className="modal-card">
            <div className="modal-header">
              <div>
                <p className="eyebrow">匹配设置</p>
                <h3 id="match-filter-title">开始匹配前，先限定岗位范围</h3>
                <p>可以先选岗位方向、是否实习、远程/现场、发布时间和经验要求，结果页也能继续改。</p>
              </div>
            </div>

            <MatchFilterForm
              initialFilters={DEFAULT_MATCH_FILTERS}
              submitLabel="开始匹配"
              onSubmit={handleStartMatching}
              isSubmitting={isRedirecting}
              onCancel={() => setIsFilterModalOpen(false)}
            />

            <div className="modal-footer">
              <button type="button" className="button-ghost" onClick={handleViewAllMatches} disabled={isRedirecting}>
                跳过筛选，直接查看全部岗位
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </>
  );
}
