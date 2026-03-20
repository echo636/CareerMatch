import { AppShell } from "@/components/layout/app-shell";
import { SectionCard } from "@/components/sections/section-card";
import { StepTimeline } from "@/components/sections/step-timeline";
import { getJobsPreview } from "@/lib/api";

const jobImportSteps = [
  "收集原始 JD",
  "批量导入后台",
  "LLM 提取结构化字段",
  "生成标准 JD JSON",
  "Embedding 向量化并写入数据库",
];

export default async function JobsAdminPage() {
  const jobs = await getJobsPreview();
  const previewJob = jobs[0] ?? null;

  return (
    <AppShell activePath="/admin/jobs">
      <SectionCard
        title="岗位数据导入"
        description="管理员侧的岗位入库面板，对应 README 中的批量导入与标准化流程。"
      >
        <div className="split-grid">
          <div className="upload-card">
            <label className="upload-dropzone" htmlFor="jobs-payload">
              <span>导入原始 JD 或 JSON 文件</span>
              <span>后续可接 CSV / Excel / API 同步任务。</span>
            </label>
            <input id="jobs-payload" type="file" className="sr-only" />
            <div className="hint-list">
              <p>标准化字段：</p>
              <ul>
                <li>技能标签</li>
                <li>项目要求</li>
                <li>薪资区间</li>
                <li>硬性条件</li>
              </ul>
            </div>
          </div>

          <div className="json-card">
            <p className="eyebrow">Demo JD JSON</p>
            <pre>{previewJob ? JSON.stringify(previewJob, null, 2) : "当前没有岗位数据。"}</pre>
          </div>
        </div>
      </SectionCard>

      <SectionCard
        title="入库流水线"
        description="前端步骤说明与后端 JobPipelineService 的处理职责一一对应。"
      >
        <StepTimeline title="岗位入库流程" steps={jobImportSteps} />
      </SectionCard>
    </AppShell>
  );
}