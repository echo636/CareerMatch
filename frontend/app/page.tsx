import Link from "next/link";

import { AppShell } from "@/components/layout/app-shell";
import { SectionCard } from "@/components/sections/section-card";
import { StepTimeline } from "@/components/sections/step-timeline";

const flowSteps = [
  "上传真实简历文件或粘贴简历文本。",
  "系统解析简历并生成结构化画像。",
  "从已导入岗位库中召回并筛选岗位。",
  "返回推荐岗位和差距分析结果。",
];

const highlights = [
  {
    title: "简历解析",
    description: "支持 PDF、DOCX、TXT、MD，并保留结构化结果供后续复用。",
  },
  {
    title: "岗位匹配",
    description: "基于已导入岗位库，完成召回、过滤和排序。",
  },
  {
    title: "差距分析",
    description: "总结技能、经验和薪资上的主要差距。",
  },
];

export default function HomePage() {
  return (
    <AppShell activePath="/">
      <section className="hero panel hero-panel">
        <div className="hero-copy">
          <p className="eyebrow">CareerMatch</p>
          <h2>上传简历，快速查看岗位匹配结果</h2>
          <p>系统会解析简历、匹配岗位，并返回简洁的差距分析结果。当前页面只保留真实流程相关内容，不展示内部调试信息。</p>
        </div>
        <div className="hero-actions">
          <Link className="primary-link" href="/resume">
            立即上传简历
          </Link>
          <Link className="secondary-link" href="/matches">
            查看结果页
          </Link>
        </div>
      </section>

      <SectionCard title="使用流程" description="从上传到结果展示，只保留用户真正需要的步骤。">
        <StepTimeline title="处理流程" steps={flowSteps} />
      </SectionCard>

      <SectionCard title="你会看到什么" description="页面结果聚焦在求职者最关心的信息。">
        <div className="card-grid">
          {highlights.map((item) => (
            <article key={item.title} className="mini-card">
              <h3>{item.title}</h3>
              <p>{item.description}</p>
            </article>
          ))}
        </div>
      </SectionCard>
    </AppShell>
  );
}
