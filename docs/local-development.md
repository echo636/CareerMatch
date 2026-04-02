# 本地开发

## 依赖

- Node.js 20+
- Python 3.11+
- Docker Desktop 或兼容容器环境

## 1. 启动基础设施

在仓库根目录执行：

```powershell
docker compose up -d
```

会启动：

- PostgreSQL: `localhost:5432`
- Qdrant: `localhost:6333`
- MinIO: `localhost:9000`

## 2. 启动后端

```powershell
cd backend
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .
Copy-Item .env.example .env
# 先按第 3 节修改 DASHSCOPE_API_KEY 和 JOB_DATA_PATH，再执行：
python run.py
```

后端默认地址：`http://localhost:5000`

说明：

- 首次启动前，先按第 3 节把 `.env` 里的 `DASHSCOPE_API_KEY` 和 `JOB_DATA_PATH` 改成可用值。
- 已预置 `FRONTEND_ORIGIN=http://localhost:3000`，浏览器可直接从前端调用后端上传接口。
- 已支持 `PDF`、`DOCX`、`TXT`、`MD` 等文本类简历的抽取。
- 旧版 `.doc` 暂不支持，建议转换为 `.docx` 后再上传。
- 原始上传文件会保存到 `backend/uploads/resumes/<resume_id>/`，后续可替换为 MinIO。
- 岗位数据通过后台脚本导入到 PostgreSQL，并同步写入 Qdrant 向量库，不再向用户暴露岗位导入接口和页面。

## 3. 导入岗位数据

当前实现里，岗位数据不是从前端页面导入，而是统一走后端导入流程：

1. 读取 `JOB_DATA_PATH` 或 `--input` 指向的岗位源文件
2. 调用 Qwen LLM 把原始 JD 结构化
3. 调用 Qwen Embedding 生成岗位向量
4. 结构化岗位写入 PostgreSQL 的 `jobs` 表
5. 岗位向量写入 Qdrant 的 `jobs` collection

### 前置条件

- `postgres` 和 `qdrant` 已启动
- `backend/.env` 已配置 `DASHSCOPE_API_KEY`
- `LLM_PROVIDER=qwen` 且 `EMBEDDING_PROVIDER=qwen`，当前代码已经移除了 mock provider
- 首次导入前，`JOB_DATA_PATH` 必须指向真实存在的文件

当前仓库里可直接用于导入的文件有：

- `data\jobs.json`
- `data\niuke_llm_cleaned.json`
- `data\zhaopin_llm_cleaned.json`
- `data\pageflux_dev_jobs_2026-03-23_172811.sql`

注意：

- `backend/.env.example` 当前默认写的是 `JOB_DATA_PATH=data/sample_jobs.json`
- 仓库里现在没有这个文件
- 如果 PostgreSQL 里的 `jobs` 表还是空表，又没有把 `JOB_DATA_PATH` 改成现有文件，后端首次启动时会因为找不到岗位源文件而失败

### 支持的数据源格式

- `.json`：支持数组，或 `{ "jobs": [...] }` 结构
- `.sql`：当前解析器按 PageFlux SQL dump 的 `COPY talent_pool.jobs ... FROM stdin;` 格式读取，不是任意 SQL 都能直接导入

其中 JSON 目前兼容三类数据：

- 已经接近标准结构的岗位 JSON
- 当前仓库里的 `niuke_llm_cleaned.json`
- 当前仓库里的 `zhaopin_llm_cleaned.json`

### 自动导入

后端启动时，如果 PostgreSQL 里的 `jobs` 表为空，会自动按 `.env` 中的 `JOB_DATA_PATH` 导入岗位数据。

推荐先显式配置：

```env
JOB_DATA_PATH=data\jobs.json
JOB_DATA_LIMIT=50
```

如果你希望启动时直接从 SQL dump 导入，可以改成：

```env
JOB_DATA_PATH=data\pageflux_dev_jobs_2026-03-23_172811.sql
JOB_DATA_LIMIT=300
```

自动导入还有三个当前实现上的规则需要注意：

- 只有在 `jobs` 表为空时才会触发自动导入
- 如果 `JOB_DATA_LIMIT` 留空，启动导入默认只会导入最多 `20` 条岗位
- 如果库里已经有岗位数据，即使你改了 `JOB_DATA_PATH`，后端启动时也不会自动重新导入

### 手动批量导入

在 `backend` 目录、激活虚拟环境后执行：

导入通用 JSON：

```powershell
python scripts\import_jobs_offline.py --input data\jobs.json --batch-size 50 --replace-jobs
```

导入牛客清洗后的 JSON：

```powershell
python scripts\import_jobs_offline.py --input data\niuke_llm_cleaned.json --limit 200 --batch-size 50 --replace-jobs
```

导入智联清洗后的 JSON：

```powershell
python scripts\import_jobs_offline.py --input data\zhaopin_llm_cleaned.json --limit 200 --batch-size 50 --replace-jobs
```

导入 SQL dump：

```powershell
python scripts\import_jobs_offline.py --input data\pageflux_dev_jobs_2026-03-23_172811.sql --limit 300 --batch-size 50 --replace-jobs
```

参数说明：

- `--input` 支持 `.json` 和 `.sql`；如果不传，脚本会回退到 `.env` 里的 `JOB_DATA_PATH`
- `--limit` 控制最多导入多少条岗位
- `--batch-size` 控制每批处理数量
- `--replace-jobs` 会先清空 PostgreSQL 里的 `jobs` 表，并删除 Qdrant 里的 `jobs` collection，然后重新导入
- 不带 `--replace-jobs` 时，会按岗位 `id` 做 upsert；相同 `id` 会更新，不同 `id` 的旧岗位会保留

大批量导入说明：

- 当前导入流程会真实调用 Qwen LLM 和 Embedding 接口
- 导入速度、费用和 `--limit`、`--batch-size`、JD 长度直接相关
- 第一次联调建议先从 `50` 到 `300` 条开始

### 导入完成后如何确认

查看 PostgreSQL 里的岗位数量：

```powershell
docker exec careermatch-postgres psql -U careermatch -d careermatch -c "select count(*) from jobs;"
```

如果你是手动执行 `scripts\import_jobs_offline.py`，脚本结束时还会打印一段 JSON，总结：

- 实际导入条数
- PostgreSQL 连接信息
- 总耗时
- 当前 `jobs` / `resumes` 表计数

## 4. 启动前端

```powershell
cd frontend
npm install
Copy-Item .env.example .env.local
npm run dev
```

前端默认地址：`http://localhost:3000`

## 5. 验证主链路

1. 打开 `http://localhost:3000/resume`
2. 上传一份真实简历 PDF / DOCX / TXT，或粘贴简历文本
3. 点击上传并等待接口返回 `resumeId`
4. 页面会跳转到 `/matches?resumeId=...`
5. 结果页展示结构化简历、岗位匹配结果、Gap 报告以及源文件元数据

## 6. 可用接口

- `GET http://localhost:5000/api/health`
- `GET http://localhost:5000/api/resumes/<resume_id>`
- `POST http://localhost:5000/api/resumes/upload`
- `POST http://localhost:5000/api/matches/recommend`
- `POST http://localhost:5000/api/gap/report`
