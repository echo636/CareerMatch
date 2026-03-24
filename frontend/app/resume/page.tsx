import { ResumeUploadForm } from "@/components/resume/resume-upload-form";
import { AppShell } from "@/components/layout/app-shell";
import { SectionCard } from "@/components/sections/section-card";
import { StepTimeline } from "@/components/sections/step-timeline";

const resumeSteps = [
  "上传文件或粘贴简历文本。",
  "系统提取正文并生成结构化简历。",
  "保存结果并生成可复用的向量数据。",
  "跳转到匹配结果页查看推荐岗位。",
];

export default function ResumePage() {
  return (
    <AppShell activePath="/resume">
      <SectionCard title="上传简历" description="提交真实简历后，系统会返回新的 resumeId，并自动进入匹配流程。">
        <ResumeUploadForm />
      </SectionCard>

      <SectionCard title="处理说明" description="这里只保留上传所需信息，不展示内部 JSON 和调试细节。">
        <StepTimeline title="简历处理流程" steps={resumeSteps} />
      </SectionCard>
    </AppShell>
  );
}
