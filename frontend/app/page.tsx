import Link from "next/link";
import { AppShell } from "@/components/layout/app-shell";
import { SectionCard } from "@/components/sections/section-card";
import { StepTimeline } from "@/components/sections/step-timeline";

const architectureLayers = [
  {
    title: "前端交互层",
    description: "负责简历上传、匹配结果查看、Gap 可视化和管理员岗位导入。",
  },
  {
    title: "业务调度层",
    description: "承接鉴权、文件上传、任务编排，以及简历/岗位处理流水线调度。",
  },
  {
    title: "AI 与算法层",
    description: "封装 LLM 解析、Embedding 向量化、召回过滤和精排打分能力。",
  },
  {
    title: "数据存储层",
    description: "组合 PostgreSQL、向量库和对象存储，承接结构化数据、向量与原始文件。",
  },
];

const endToEndFlow = [
  "用户上传 PDF / Word 简历",
  "文本解析并生成标准化 CV JSON",
  "Embedding 向量化后写入向量库",
  "召回 Top N 岗位并执行规则过滤",
  "输出可解释评分与 Gap 报告",
];

export default function HomePage() {
  return (
    <AppShell activePath="/">
      <section className="hero panel hero-panel">
        <div className="hero-copy">
          <p className="eyebrow">系统总览</p>
          <h2>从简历解析到岗位匹配，再到能力差距分析的完整闭环</h2>
          <p>
            当前骨架按 README 的分层架构拆分为 Next.js 前端、Flask 业务接口层、AI
            服务层和存储层，并为每个核心流程预留了可直接扩展的模块入口。
          </p>
        </div>
        <div className="hero-actions">
          <Link className="primary-link" href="/resume">
            查看简历流水线
          </Link>
          <Link className="secondary-link" href="/matches">
            查看匹配结果页
          </Link>
        </div>
      </section>

      <SectionCard
        title="核心分层"
        description="每一层都对应 README 中的职责拆分，避免把接口、算法和数据访问堆在一起。"
      >
        <div className="card-grid">
          {architectureLayers.map((layer) => (
            <article key={layer.title} className="mini-card">
              <h3>{layer.title}</h3>
              <p>{layer.description}</p>
            </article>
          ))}
        </div>
      </SectionCard>

      <SectionCard
        title="主业务流程"
        description="按岗位入库、简历处理、匹配与 Gap 分析四条主链路组织代码。"
      >
        <StepTimeline title="匹配主链路" steps={endToEndFlow} />
      </SectionCard>

      <SectionCard
        title="进入各功能面板"
        description="用户端、算法结果页和管理员端已分别拆成独立路由，便于继续接接口和表单动作。"
      >
        <div className="quick-links">
          <Link href="/resume" className="quick-link-card">
            <strong>简历处理</strong>
            <span>上传、解析、结构化 JSON 预览</span>
          </Link>
          <Link href="/matches" className="quick-link-card">
            <strong>匹配结果</strong>
            <span>Top N 结果、解释性评分、Gap 报告</span>
          </Link>
          <Link href="/admin/jobs" className="quick-link-card">
            <strong>岗位导入</strong>
            <span>批量 JD 入库、标准化与向量化</span>
          </Link>
        </div>
      </SectionCard>
    </AppShell>
  );
}
