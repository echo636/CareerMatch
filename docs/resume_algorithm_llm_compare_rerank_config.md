# `resume_algorithm_llm_compare.py` 配置说明

这个文档只针对脚本：

`backend/test/test_resume_algorithm_llm_compare.py`

现在它的本地配置已经统一到一个文件：

`backend/test/local_test_config.py`

你以后改简历默认值、改 rerank 模型、切回后端默认模型，都只需要改这一个文件。

## 配置文件结构

`backend/test/local_test_config.py` 里现在有一个顶层对象：

```python
LOCAL_TEST_CONFIG
```

它分成两个分组：

```python
LOCAL_TEST_CONFIG.resume
LOCAL_TEST_CONFIG.rerank
```

这样比一堆平铺常量更容易读。

## 1. 简历相关配置

位置：

```python
LOCAL_TEST_CONFIG.resume
```

字段：

- `default_resume_id`
  - 单简历脚本默认使用的简历 ID

- `default_resume_file`
  - 单简历脚本默认使用的简历文件路径
  - 如果 `default_resume_id` 和 `default_resume_file` 同时设置，单简历脚本优先用文件路径

- `default_resume_ids`
  - 多简历脚本默认使用的简历 ID 列表

示例：

```python
LOCAL_TEST_CONFIG.resume.default_resume_id = ""
LOCAL_TEST_CONFIG.resume.default_resume_file = r"D:\constructing_projects\CareerMatch\backend\uploads\resumes\resume-393061ce\e31efb4b_15-24K_10.pdf"
LOCAL_TEST_CONFIG.resume.default_resume_ids = []
```

## 2. Rerank 模型配置

位置：

```python
LOCAL_TEST_CONFIG.rerank
```

注意：

这部分只影响：

`backend/test/test_resume_algorithm_llm_compare.py`

也就是最后的 LLM rerank / compare 阶段。

下面这些仍然走后端原有配置：

- `build_services(...)`
- 简历补解析
- embedding
- 向量召回
- 岗位导入

## 两种 rerank 模式

### `backend_client`

复用后端 `.env` 当前的 LLM 客户端。

适合：

- 你只想沿用后端当前模型
- 不想给测试脚本额外配置 API

示例：

```python
LOCAL_TEST_CONFIG.rerank.source = "backend_client"
LOCAL_TEST_CONFIG.rerank.provider = "backend"
LOCAL_TEST_CONFIG.rerank.model = ""
```

说明：

- `model=""` 时，报告里会显示后端当前模型名
- 真实请求仍然由后端当前 LLM 客户端发出

### `openai_compatible`

测试脚本直接请求一个兼容 `chat/completions` 的外部接口。

适合：

- 单独把 rerank 切到 MiniMax
- 不想改后端全局 `LLM_PROVIDER`

示例：

```python
LOCAL_TEST_CONFIG.rerank.source = "openai_compatible"
LOCAL_TEST_CONFIG.rerank.provider = "minimax"
LOCAL_TEST_CONFIG.rerank.model = "MiniMax-Text-01"
LOCAL_TEST_CONFIG.rerank.chat_url = "https://your-endpoint/chat/completions"
LOCAL_TEST_CONFIG.rerank.api_key = "your_api_key"
LOCAL_TEST_CONFIG.rerank.timeout_sec = 120
LOCAL_TEST_CONFIG.rerank.retry_count = 2
LOCAL_TEST_CONFIG.rerank.retry_backoff_sec = 2.0
LOCAL_TEST_CONFIG.rerank.temperature = 0.1
LOCAL_TEST_CONFIG.rerank.auth_header_name = "Authorization"
LOCAL_TEST_CONFIG.rerank.auth_prefix = "Bearer "
LOCAL_TEST_CONFIG.rerank.request_headers = {}
LOCAL_TEST_CONFIG.rerank.extra_body = {
    "response_format": {"type": "json_object"},
}
```

## 每个 rerank 参数怎么改

文件：

`backend/test/local_test_config.py`

对象：

`LOCAL_TEST_CONFIG.rerank`

字段说明：

- `source`
  - 可选：`"backend_client"` 或 `"openai_compatible"`
  - 决定 rerank 请求从哪里发出

- `provider`
  - 写进报告里的 provider 名称
  - 例如：`"minimax"`、`"qwen"`、`"openai"`

- `model`
  - 写进报告里的模型名
  - 在 `openai_compatible` 模式下，也会作为请求里的 `model`

- `chat_url`
  - 外部模型的完整 `chat/completions` URL
  - 只在 `openai_compatible` 模式使用

- `api_key`
  - 外部模型 API key
  - 只在 `openai_compatible` 模式使用

- `timeout_sec`
  - 单次请求超时秒数

- `retry_count`
  - 失败后重试次数

- `retry_backoff_sec`
  - 每次重试前等待秒数

- `temperature`
  - 请求里的 `temperature`

- `auth_header_name`
  - 认证头名称，默认是 `Authorization`

- `auth_prefix`
  - 认证前缀，默认是 `Bearer `

- `request_headers`
  - 额外请求头

- `extra_body`
  - 额外请求体字段
  - 默认保留 `response_format={"type":"json_object"}`

## 推荐用法

### 以后切 MiniMax

只改：

`backend/test/local_test_config.py`

把 rerank 相关字段改成：

```python
LOCAL_TEST_CONFIG.rerank.source = "openai_compatible"
LOCAL_TEST_CONFIG.rerank.provider = "minimax"
LOCAL_TEST_CONFIG.rerank.model = "你的 MiniMax 模型名"
LOCAL_TEST_CONFIG.rerank.chat_url = "你的 MiniMax chat/completions 地址"
LOCAL_TEST_CONFIG.rerank.api_key = "你的 key"
```

其他参数先保持默认就够了。

### 以后切回后端默认模型

只改：

```python
LOCAL_TEST_CONFIG.rerank.source = "backend_client"
LOCAL_TEST_CONFIG.rerank.provider = "backend"
LOCAL_TEST_CONFIG.rerank.model = ""
```

## 运行方式

```bash
python backend\test\test_resume_algorithm_llm_compare.py
```

如果你还想固定简历文件，也是在同一个文件里改：

`backend/test/local_test_config.py`

## 报告里会显示什么

报告头部现在会显示：

- `LLM Source`
- `LLM Provider`
- `LLM Model`

这样回看报告时，你能直接知道这次 rerank 用的是哪套配置。

## 常见排查

如果用 `openai_compatible` 模式报错，先检查：

1. `LOCAL_TEST_CONFIG.rerank.chat_url` 是否完整可访问
2. `LOCAL_TEST_CONFIG.rerank.api_key` 是否正确
3. `LOCAL_TEST_CONFIG.rerank.model` 是否是平台真实可用模型名
4. 该接口是否真的兼容 `chat/completions`
5. 返回内容里是否包含可解析的 JSON 文本
