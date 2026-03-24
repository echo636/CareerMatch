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
python run.py
```

后端默认地址：`http://localhost:5000`

说明：

- 已预置 `FRONTEND_ORIGIN=http://localhost:3000`，浏览器可直接从前端调用后端上传接口。
- 已支持 `PDF`、`DOCX`、`TXT`、`MD` 等文本类简历的抽取。
- 旧版 `.doc` 暂不支持，建议转换为 `.docx` 后再上传。
- 原始上传文件会保存到 `backend/uploads/resumes/<resume_id>/`，后续可替换为 MinIO。
- 岗位数据通过后台脚本导入到 SQLite 持久化库，不再向用户暴露岗位导入接口和页面。

## 3. 启动前端

```powershell
cd frontend
npm install
Copy-Item .env.example .env.local
npm run dev
```

前端默认地址：`http://localhost:3000`

## 4. 验证主链路

1. 打开 `http://localhost:3000/resume`
2. 上传一份真实简历 PDF / DOCX / TXT，或粘贴简历文本
3. 点击上传并等待接口返回 `resumeId`
4. 页面会跳转到 `/matches?resumeId=...`
5. 结果页展示结构化简历、岗位匹配结果、Gap 报告以及源文件元数据

## 5. 可用接口

- `GET http://localhost:5000/api/health`
- `GET http://localhost:5000/api/resumes/<resume_id>`
- `POST http://localhost:5000/api/resumes/upload`
- `POST http://localhost:5000/api/matches/recommend`
- `POST http://localhost:5000/api/gap/report`
