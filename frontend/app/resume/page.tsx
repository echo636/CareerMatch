import { ResumeUploadForm } from "@/components/resume/resume-upload-form";
import { AppShell } from "@/components/layout/app-shell";
import { SectionCard } from "@/components/sections/section-card";
import { StepTimeline } from "@/components/sections/step-timeline";
import { getResumePreview } from "@/lib/api";

const resumeSteps = [
  "上传 PDF / DOCX 或粘贴简历文本",
  "抽取文本并落盘原始文件",
  "LLM 输出标准化 CV JSON",
  "向量化后写入向量库",
  "进入岗位召回与评分流程",
];

export default async function ResumePage() {
  const resume = await getResumePreview();

  return (
    <AppShell activePath="/resume">
      <SectionCard
        title="简历处理工作台"
        description="这一页已经接通到后端上传接口。提交后会生成新的 resumeId，并跳转到匹配结果页。"
      >
        <div className="split-grid">
          <div className="upload-card">
            <p className="eyebrow">真实链路</p>
            <ResumeUploadForm />
          </div>

          <div className="json-card">
            <p className="eyebrow">Demo CV JSON</p>
            <pre>{JSON.stringify(resume, null, 2)}</pre>
          </div>
        </div>
      </SectionCard>

      <SectionCard
        title="处理流水线"
        description="上传文件会先做文本抽取，再把原始文件保存到本地对象存储目录，便于后续切换到 MinIO。"
      >
        <StepTimeline title="简历解析流程" steps={resumeSteps} />
      </SectionCard>
    </AppShell>
  );
}