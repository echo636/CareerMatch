# 项目骨架说明

该骨架直接对应 README 中的四层设计：前端交互层、业务调度层、AI 与算法层、数据存储层。

## 目录结构

```text
CareerMatch/
├─ frontend/
│  ├─ app/
│  │  ├─ admin/jobs/
│  │  ├─ matches/
│  │  └─ resume/
│  ├─ components/
│  ├─ lib/
│  └─ types/
├─ backend/
│  ├─ app/
│  │  ├─ api/routes/
│  │  ├─ clients/
│  │  ├─ core/
│  │  ├─ domain/
│  │  ├─ repositories/
│  │  └─ services/
│  ├─ data/
│  └─ uploads/
├─ docs/
└─ docker-compose.yml
```

## 前端职责

- `frontend/app/`：按用户流拆页面，覆盖系统总览、简历处理、匹配结果、岗位导入。
- `frontend/components/`：沉淀共享布局、卡片、评分、上传表单与图表占位组件。
- `frontend/lib/api.ts`：提供对后端 API 的调用入口；展示页支持 demo fallback，上传链路要求后端在线。
- `frontend/types/`：统一前端领域类型，避免页面直接拼装业务结构。

## 后端职责

- `backend/app/api/routes/`：Flask Blueprint 路由层，负责 HTTP 输入输出。
- `backend/app/services/`：简历处理、岗位入库、匹配打分、Gap 分析等核心业务编排。
- `backend/app/clients/`：LLM、Embedding、向量存储、文档解析器和对象存储的适配层。
- `backend/app/repositories/`：仓储层，当前使用内存实现，后续可替换为 PostgreSQL / Qdrant。
- `backend/app/domain/`：领域模型与序列化逻辑，保证 API 输出和内部结构解耦。

## 当前 API 入口

- `GET /api/health`
- `GET /api/resumes/demo`
- `GET /api/resumes/<resume_id>`
- `POST /api/resumes/upload`
- `GET /api/jobs`
- `POST /api/jobs/import`
- `POST /api/matches/recommend`
- `POST /api/gap/report`

## 已接通的主链路

1. 前端简历处理页提交文本或文件。
2. 后端为 PDF / DOCX / TXT 执行文本抽取，并保存原始文件到本地对象存储目录。
3. 后端生成结构化简历并写入内存仓储与向量索引。
4. 匹配结果页按 `resumeId` 拉取真实简历、匹配结果与 Gap 报告。
5. 前端展示可解释得分、技能缺口、岗位对照信息和源文件元数据。

## 下一步建议

1. 把 `LocalObjectStorageClient` 替换为 MinIO / S3。
2. 把 `JobRepository` 和 `ResumeRepository` 替换为 PostgreSQL 持久化实现。
3. 把 `InMemoryVectorStore` 替换为 Qdrant 或 pgvector。
4. 为扫描件 PDF 增加 OCR 流程。