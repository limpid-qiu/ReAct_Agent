# ReAct Agent

基于 FastAPI、LangChain/LangGraph ReAct Agent、RAG 和 Chroma 的智能问答服务。项目包含聊天接口、流式输出、会话持久化、知识库检索、文档入库、工具调用治理、权限校验、限流、日志、Prometheus 指标和简单前端页面。

## 功能特性

- ReAct Agent：支持模型推理和工具调用。
- RAG 知识库：支持 txt、pdf、docx 文档上传、切片、向量入库和检索问答。
- 会话管理：保存会话和消息，支持 conversation_id 续聊。
- 多租户上下文：通过请求头区分 user、tenant 和 knowledge base。
- 工具治理：工具注册、权限校验、参数校验、重试、fallback、日志和审计。
- 安全能力：API Key、权限点、Prompt Injection 风险记录、上传文件校验。
- 可观测性：结构化日志、监控概览、工具审计和 Prometheus 指标。
- Web UI：内置静态前端，可通过 `/ui` 访问。

## 技术栈

- Python 3
- FastAPI / Uvicorn
- SQLAlchemy / SQLite
- LangChain / LangGraph
- ChromaDB
- DashScope
- Pydantic Settings
- Prometheus Client

## 项目结构

```text
agent/               Agent 核心和工具系统
app/                 FastAPI 后端服务
  api/               HTTP 接口
  core/              配置、安全、日志、限流、指标
  db/                数据库连接、初始化和模型
  schemas/           请求和响应模型
  services/          业务服务层
config/              YAML 配置文件
docs/                项目文档
frontend/            简单前端页面
model/               模型工厂
prompts/             提示词
rag/                 RAG 和向量库逻辑
scripts/             辅助脚本
utils/               通用工具
```

运行时数据目录如 `data/`、`chroma_db/`、`logs/` 不建议提交到 Git。

## 快速开始

### 1. 创建并激活虚拟环境

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

如果你已经在 Conda 或其他虚拟环境中，可以跳过这一步。

### 2. 安装依赖

```powershell
pip install -r requirements.txt
```

### 3. 配置环境变量

在项目根目录创建 `.env` 文件，按需填写：

```env
APP_ENV=dev
APP_NAME=ReAct Agent API
APP_VERSION=0.1.0
DEBUG=true
HOST=127.0.0.1
PORT=8000

API_KEY=your-local-api-key
DATABASE_URL=sqlite:///./data/app.db

MODEL_MAX_CONCURRENT=3
CHAT_USER_RATE_LIMIT=20
CHAT_TENANT_RATE_LIMIT=100
CHAT_RATE_LIMIT_WINDOW_SECONDS=60

KNOWLEDGE_UPLOAD_DIR=data/uploads
MAX_UPLOAD_FILE_SIZE_MB=20

DASHSCOPE_API_KEY=your-dashscope-api-key
AMAP_KEY=your-amap-key

SECURITY_STRICT_MODE=false
ALLOW_DEMO_HEADERS=true
ALLOW_EMPTY_TOOL_PERMISSIONS=true
```

注意：`.env`、`.env.example`、`config/api_keys.yml` 等可能包含敏感信息，已经建议放进 `.gitignore`，不要上传到公开仓库。

### 4. 启动服务

```powershell
uvicorn app.main:app --reload
```

默认访问地址：

- API 根路径：http://127.0.0.1:8000/
- Swagger 文档：http://127.0.0.1:8000/docs
- 前端页面：http://127.0.0.1:8000/ui
- 健康检查：http://127.0.0.1:8000/api/health
- Prometheus 指标：http://127.0.0.1:8000/metrics

也可以直接运行：

```powershell
python -m app.main
```

## 请求头说明

多数业务接口需要请求上下文。开发环境默认允许使用演示请求头：

```text
X-User-ID: demo_user
X-Tenant-ID: demo_tenant
X-Knowledge-Base-ID: kb_default_demo_tenant
X-API-Key: your-local-api-key
```

如果 `API_KEY` 为空，则本地开发可不启用 API Key 鉴权。生产环境建议开启严格鉴权，并从可信身份系统或 API Key 绑定关系解析用户和租户。

## 常用接口

### 健康检查

```powershell
curl http://127.0.0.1:8000/api/health
```

### 普通聊天

```powershell
curl -X POST "http://127.0.0.1:8000/api/chat/" ^
  -H "Content-Type: application/json" ^
  -H "X-User-ID: demo_user" ^
  -H "X-Tenant-ID: demo_tenant" ^
  -d "{\"query\":\"推荐一款适合小户型的扫地机器人\",\"history\":[]}"
```

响应示例：

```json
{
  "answer": "这里是 Agent 返回的回答",
  "request_id": "req_xxx",
  "conversation_id": "conv_xxx"
}
```

### 流式聊天

```powershell
curl -X POST "http://127.0.0.1:8000/api/chat/stream" ^
  -H "Content-Type: application/json" ^
  -H "X-User-ID: demo_user" ^
  -H "X-Tenant-ID: demo_tenant" ^
  -d "{\"query\":\"解释一下 RAG 是什么\",\"history\":[]}"
```

### 创建知识库

```powershell
curl -X POST "http://127.0.0.1:8000/api/knowledge/bases" ^
  -H "Content-Type: application/json" ^
  -H "X-User-ID: demo_user" ^
  -H "X-Tenant-ID: demo_tenant" ^
  -d "{\"name\":\"默认知识库\",\"description\":\"本地测试知识库\"}"
```

### 上传文档入库

```powershell
curl -X POST "http://127.0.0.1:8000/api/knowledge/documents/upload" ^
  -H "X-User-ID: demo_user" ^
  -H "X-Tenant-ID: demo_tenant" ^
  -H "X-Knowledge-Base-ID: kb_default_demo_tenant" ^
  -F "file=@docs/project_tutorial.md"
```

上传接口支持 `.txt`、`.pdf`、`.docx`。上传成功后会创建后台入库任务。

### 查询知识库

```powershell
curl -X POST "http://127.0.0.1:8000/api/knowledge/search" ^
  -H "Content-Type: application/json" ^
  -H "X-User-ID: demo_user" ^
  -H "X-Tenant-ID: demo_tenant" ^
  -H "X-Knowledge-Base-ID: kb_default_demo_tenant" ^
  -d "{\"query\":\"项目的 Agent 调用链路是什么？\"}"
```

### 监控概览

```powershell
curl "http://127.0.0.1:8000/api/monitoring/overview" ^
  -H "X-User-ID: demo_user" ^
  -H "X-Tenant-ID: demo_tenant"
```

## 核心链路

一次聊天请求的大致流程：

```text
用户请求
 -> app/api/chat.py
 -> app/services/agent_service.py
 -> agent/react_agent.py
 -> 大模型 / 工具 / RAG
 -> 保存会话和审计记录
 -> 返回回答
```

RAG 查询链路：

```text
Agent 调用 rag_summarize 工具
 -> RagSummarizeService
 -> VectorStoreService
 -> Chroma 检索
 -> 拼接上下文
 -> 调用模型生成答案
 -> 返回引用来源
```

## Git 忽略建议

建议 `.gitignore` 至少包含：

```gitignore
.env
.env.example

__pycache__/
*.pyc
*.pyo
*.pyd

.vscode/
%SystemDrive%/

logs/
*.log

chroma_db/
data/
*.db
*.sqlite3

config/api_keys.yml
```

这样可以避免把本地密钥、数据库、向量库、上传文件、日志和缓存提交到 GitHub。

## 进一步阅读

- `docs/project_tutorial.md`：项目学习教程和模块拆解。
- `docs/phase3_rag_verification.md`：RAG 能力验证。
- `docs/phase4_tool_registry_design.md`：工具注册和治理设计。
- `docs/phase5_observability_verification.md`：可观测性验证。
- `docs/phase6_security_verification.md`：安全能力验证。

