# 项目架构说明

本文档描述当前 CareerMatch 的主要目录职责、核心接口以及真实数据链路。

## 目录结构

```text
CareerMatch/
├── frontend/
│   ├── app/
│   │   ├── matches/
│   │   └── resume/
│   ├── components/
│   ├── lib/
│   └── types/
├── backend/
│   ├── app/
│   │   ├── api/routes/
│   │   ├── clients/
│   │   ├── core/
│   │   ├── domain/
│   │   ├── repositories/
│   │   └── services/
│   ├── data/
│   ├── uploads/
│   └── import_jobs_offline.py
├── docs/
└── docker-compose.yml
```

## 前端职责

- `frontend/app/`：页面入口，仅保留简历上传与匹配结果视图。
- `frontend/components/`：共享布局、卡片、分数展示、上传表单和图表组件。
- `frontend/lib/api.ts`：封装后端公开接口调用，仅包含用户需要的上传、匹配和 Gap 查询。
- `frontend/types/`：统一前端领域类型。

## 后端职责

- `backend/app/api/routes/`：Flask Blueprint 路由层，处理 HTTP 输入输出。
- `backend/app/services/`：简历处理、匹配评分、Gap 分析等业务编排。
- `backend/app/clients/`：LLM、Embedding、向量存储、文档解析器和对象存储适配层。
- `backend/app/repositories/`：使用 PostgreSQL（JSONB）持久化结构化简历和岗位数据。
- `backend/app/domain/`：领域模型与序列化逻辑。
- `backend/import_jobs_offline.py`：后台离线岗位导入脚本，直接完成结构化、embedding 和持久化。

## 当前 API 接口

- `GET /api/health`
- `GET /api/resumes/<resume_id>`
- `POST /api/resumes/upload`
- `POST /api/matches/recommend`
- `POST /api/gap/report`

## 当前主链路

1. 前端在 `/resume` 上传真实简历文件或文本。
2. 后端解析文件文本，落盘原始文件，并生成结构化简历 JSON。
3. 后端生成或复用该简历的 embedding，向量持久化到 Qdrant，结构化数据持久化到 PostgreSQL。
4. 岗位数据通过后台离线脚本导入 PostgreSQL 和 Qdrant。
5. 匹配页按 `resumeId` 拉取真实简历、匹配结果和 Gap 报告。
6. Gap 分析依赖当前召回并通过过滤的岗位结果生成。

## 后续建议

1. 为离线导入脚本增加重试、断点续跑和统计输出。
2. 为扫描版 PDF 增加 OCR 流程。
3. 为后台岗位导入增加任务调度和状态监控。
4. 将本地文件存储替换为 MinIO。
