"use client";

import type { ChangeEvent, FormEvent } from "react";
import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import type { Route } from "next";

import { uploadResume } from "@/lib/api";

export function ResumeUploadForm() {
  const router = useRouter();
  const [selectedFileName, setSelectedFileName] = useState("未选择文件");
  const [error, setError] = useState<string | null>(null);
  const [isPending, startTransition] = useTransition();

  function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
    const nextFile = event.target.files?.[0];
    setSelectedFileName(nextFile?.name ?? "未选择文件");
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);

    const form = event.currentTarget;
    const formData = new FormData(form);
    const content = String(formData.get("content") ?? "").trim();
    const file = formData.get("file");
    const hasFile = file instanceof File && file.size > 0;

    if (!content && !hasFile) {
      setError("请粘贴简历文本，或至少选择一个 PDF / DOCX / TXT / MD 文件。");
      return;
    }

    startTransition(() => {
      void submit(formData);
    });
  }

  async function submit(formData: FormData) {
    try {
      const payload = await uploadResume(formData);
      router.push(`/matches?resumeId=${encodeURIComponent(payload.resumeId)}` as Route);
      router.refresh();
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "上传失败，请稍后重试。");
    }
  }

  return (
    <form className="form-stack" onSubmit={handleSubmit}>
      <div className="field-group">
        <label className="field-label" htmlFor="resume-content">
          简历文本
        </label>
        <textarea
          id="resume-content"
          name="content"
          className="field-textarea"
          placeholder="推荐直接粘贴可复制的简历正文。如果同时上传文件，这里的文本会优先作为解析输入。"
          rows={12}
        />
        <p className="field-help">后端已支持 PDF、DOCX 和常见 UTF-8 / GB18030 文本文件。旧版 .doc 暂不支持。</p>
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

      {error ? <p className="status-message status-error">{error}</p> : null}

      <div className="button-row">
        <button type="submit" className="button-primary" disabled={isPending}>
          {isPending ? "正在解析并生成匹配结果..." : "上传并查看匹配结果"}
        </button>
      </div>
    </form>
  );
}