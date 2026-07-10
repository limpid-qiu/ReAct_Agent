# ReAct Agent 企业级上线改造方案

## 1. 项目现状

当前项目是一个本地可运行的 ReAct Agent + RAG 原型，已经具备以下基础能力：

- 基于 LangChain / LangGraph 的 ReAct Agent 执行流程。
- 基于 Chroma 的本地向量库检索。
- 支持本地知识文件加载，包括 txt、pdf、docx。
- Chat Model 与 Embedding Model 已通过工厂类封装。
- Prompt 与配置文件已外置。
- 已有基础日志与工具调用中间件。
- Agent 支持流式输出雏形。

当前项目更接近单机实验或 Demo 形态，距离企业级可上线系统还缺少：

- API 服务层。
- 多用户与多租户隔离。
- 会话与消息持久化。
- 高并发请求治理。
- 异步任务队列。
- 生产级数据库。
- 权限认证与安全控制。
- 可观测性体系。
- 测试、部署、CI/CD。
- RAG 数据治理与检索质量评估。
- 模型调用限流、重试、超时、熔断与降级。

## 2. 企业级改造目标

企业级项目的核心目标不是只让功能可用，而是让系统做到：

- 可服务化：通过标准 API 对外提供能力。
- 可并发：支持多用户同时访问和高强度 IO。
- 可隔离：不同用户、租户、知识库之间数据隔离。
- 可观测：能追踪每次请求、模型调用、工具调用和检索过程。
- 可治理：权限、安全、审计、限流、成本可控。
- 可部署：支持容器化、环境隔离、CI/CD。
- 可演进：模块边界清晰，便于替换模型、向量库、工具和业务流程。

## 3. 推荐目标架构

```text
前端 / 企业系统 / API Client
        |
        v
API Gateway / FastAPI 服务
        |
        +-- Auth 鉴权 / 租户识别 / 限流
        |
        +-- Chat API
        |     |
        |     +-- Conversation Service
        |     +-- Agent Runtime
        |     +-- Tool Registry
        |     +-- RAG Service
        |
        +-- Knowledge API
        |     |
        |     +-- 文件上传
        |     +-- 文档解析
        |     +-- 切片
        |     +-- Embedding
        |     +-- 向量入库
        |
        +-- Admin API
              |
              +-- 模型配置
              +-- Prompt 配置
              +-- 日志审计
              +-- 知识库管理

基础设施：
PostgreSQL / MySQL
Redis
Celery / RQ / Dramatiq
向量数据库：Milvus / Qdrant / pgvector / 企业版 Chroma
对象存储：MinIO / S3
Prometheus + Grafana
ELK / Loki
Docker / Kubernetes
```

## 4. 第一阶段：服务化改造

当前 Agent 是本地进程内调用，生产环境应改造成标准 Web 服务。

推荐使用 FastAPI 作为服务层：

```text
app/
  main.py
  api/
    chat.py
    knowledge.py
    health.py
  services/
    agent_service.py
    rag_service.py
    conversation_service.py
  schemas/
    chat.py
    knowledge.py
  core/
    config.py
    logging.py
    security.py
```

建议提供的基础接口：

- `POST /api/chat`
- `POST /api/chat/stream`
- `GET /api/conversations/{id}`
- `POST /api/knowledge/upload`
- `POST /api/knowledge/rebuild`
- `GET /health`
- `GET /metrics`

面试表达：

> 原型阶段 Agent 是进程内直接调用的，上线时我会把它抽象成无状态服务，通过 FastAPI 暴露同步和流式接口。会话、用户、知识库元数据放到数据库，Agent Runtime 只负责执行，不持有不可控的全局业务状态。

## 5. 第二阶段：多用户与高并发

### 5.1 用户与租户隔离

每次请求都应携带或解析出以下上下文：

- `user_id`
- `tenant_id`
- `conversation_id`
- `knowledge_base_id`
- `request_id`

RAG 检索和工具调用都必须基于这些上下文进行权限过滤。

推荐知识库隔离维度：

```text
tenant_id + knowledge_base_id + document_id
```

避免出现 A 用户检索到 B 用户资料的问题。

### 5.2 会话持久化

不要长期依赖请求里的 `history` list，应使用数据库持久化会话与消息。

推荐核心表：

```text
users
tenants
conversations
messages
tool_calls
agent_runs
documents
knowledge_chunks
```

### 5.3 长任务异步化

文档上传、PDF 解析、Embedding、知识库重建都属于高 IO 或高耗时任务，不应阻塞 API 请求。

推荐流程：

```text
用户上传文件
  -> API 保存文件到对象存储
  -> 创建 document 记录
  -> 投递解析任务
  -> Worker 解析、切片、Embedding、入库
  -> 更新任务状态
```

推荐技术：

- Redis + Celery
- Redis Queue
- Dramatiq

### 5.4 限流、排队与削峰

模型 API 是昂贵且不稳定的外部资源，需要治理：

- 用户级限流。
- 租户级限流。
- 模型级并发限制。
- 请求超时控制。
- 自动重试。
- 熔断。
- 降级模型。
- 队列削峰。

可选实现：

- Redis token bucket。
- `asyncio.Semaphore`。
- API Gateway 限流。
- Celery 队列削峰。

## 6. 第三阶段：RAG 企业级改造

### 6.1 多租户知识库

向量数据需要支持 namespace 或 metadata filter。

推荐 metadata：

```text
tenant_id
knowledge_base_id
document_id
chunk_id
user_id
permission_scope
source
version
created_at
```

### 6.2 文档版本管理

当前项目使用 `md5.txt` 记录文件是否加载过，生产环境应改成数据库管理。

推荐字段：

```text
document_id
tenant_id
knowledge_base_id
file_name
file_hash
version
status
created_by
created_at
parsed_at
indexed_at
```

### 6.3 增量更新

文件发生变化时应支持：

- 删除旧 chunk。
- 写入新 chunk。
- 保留历史版本。
- 支持回滚。
- 记录重建日志。

### 6.4 检索质量提升

从简单 top-k 检索逐步升级：

- query rewrite。
- hybrid search：关键词 + 向量。
- rerank。
- metadata filter。
- 返回 citation 引用来源。
- answer grounding，减少幻觉。
- 离线评估集与命中率评估。

面试表达：

> RAG 不只是向量库查询，我会把它拆成 ingestion pipeline 和 retrieval pipeline。前者保证文档可追踪、可重建、可回滚；后者保证检索可控、可解释、可评估。

## 7. 第四阶段：Agent 工具治理

当前工具直接挂在 Agent 上，企业级系统应建立工具注册与权限体系。

推荐 Tool Registry：

```text
tool_name
description
input_schema
timeout
retry_policy
permission
audit_enabled
enabled
```

工具调用需要治理：

- 参数校验。
- 超时控制。
- 异常包装。
- 敏感信息脱敏。
- 用户权限校验。
- 调用日志。
- 幂等性。
- 外部接口失败降级。

面试常见追问：

- Agent 调用了危险工具怎么办？
- 工具超时怎么办？
- 多租户是否能调用同一套工具？
- 工具调用记录怎么审计？
- 工具参数如何防注入？

## 8. 第五阶段：稳定性与可观测性

企业级系统必须能定位问题，而不是只知道“模型没返回”。

需要观测的数据：

- request_id。
- user_id / tenant_id。
- conversation_id。
- Agent run 耗时。
- 模型调用耗时。
- token 消耗。
- 工具调用次数。
- 工具调用成功率。
- RAG 检索耗时。
- RAG 命中文档。
- 向量库查询耗时。
- Worker 队列堆积量。
- P95 / P99 延迟。
- 错误率。

推荐技术：

- Logging：structlog / loguru / JSON logging。
- Metrics：Prometheus。
- Dashboard：Grafana。
- Trace：OpenTelemetry。
- Error Tracking：Sentry。
- Log Storage：ELK / Loki。

## 9. 第六阶段：安全与权限

企业级上线必须补齐安全体系。

建议实现：

- JWT / OAuth2 / 企业 SSO。
- RBAC 权限模型。
- API key 管理。
- 环境变量或 Secret Manager 管理密钥。
- Prompt injection 防护。
- 文件上传白名单。
- 文件大小限制。
- 文档内容安全扫描。
- 工具调用权限控制。
- 日志脱敏。
- 租户数据隔离。

注意：

- `.env` 不应提交真实密钥。
- 日志中不能打印用户敏感数据、完整 prompt、完整工具参数。
- RAG 检索必须带租户和权限过滤。

## 10. 第七阶段：部署工程化

需要补齐标准工程文件：

```text
requirements.txt / pyproject.toml
Dockerfile
docker-compose.yml
.env.example
alembic migrations
pytest
pre-commit
ruff / black / mypy
GitHub Actions / GitLab CI
```

推荐生产组件：

```text
Nginx
FastAPI + Uvicorn/Gunicorn
Redis
PostgreSQL
Vector DB
Worker
Object Storage
Monitoring
```

容器拆分：

```text
api-service
worker-service
scheduler-service
postgres
redis
vector-db
minio
prometheus
grafana
```

## 11. 推荐落地路线

### M1：能上线的最小服务版

- 修复现有代码 bug。
- 增加依赖管理文件。
- 增加 FastAPI 服务层。
- 增加 `/api/chat/stream`。
- 增加 `/health`。
- 配置从环境变量读取。
- 增加 Dockerfile。

### M2：多人可用版

- 增加用户、会话、消息表。
- 接入 PostgreSQL。
- RAG 增加 `tenant_id` / `knowledge_base_id` 过滤。
- 增加 Redis 限流。
- 日志增加 `request_id`。

### M3：企业知识库版

- 增加文件上传 API。
- 文档解析改为异步任务。
- Embedding 入库改为异步任务。
- 增加文档状态管理。
- 增加引用来源返回。
- 增加知识库版本管理。

### M4：生产增强版

- 增加 Prometheus 指标。
- 增加 OpenTelemetry 链路追踪。
- 增加工具权限系统。
- 增加 Prompt injection 基础防护。
- 增加 CI/CD。
- 增加压测。
- 增加灰度发布。
- 增加模型降级和熔断。

## 12. 面试拷打点

重点准备以下问题：

- 多用户数据如何隔离？
- 高并发下模型调用怎么限流？
- 流式输出怎么实现？
- 文档上传后怎么异步入库？
- 向量库如何支持增量更新？
- RAG 如何减少幻觉？
- Agent 工具调用如何审计和限权？
- 模型 API 超时怎么办？
- 如何观测一次 Agent 调用全过程？
- 如何评估 RAG 效果？
- 如何做灰度发布和回滚？
- 如何防止 prompt injection？
- 为什么本地 Chroma 不适合直接上生产？
- 为什么需要 Redis / 队列 / 数据库？
- 如何控制 token 成本？
- 如何处理第三方模型服务不可用？

## 13. 总结

这个项目不建议一开始全量重写。更稳妥的路径是保留当前 `agent`、`rag`、`model` 的核心能力，在外层逐步补齐企业工程能力：

```text
FastAPI + PostgreSQL + Redis + Worker + Vector DB + Observability + Docker
```

这样既能快速从 Demo 演进为可上线服务，也能在面试中清楚说明从原型到生产系统的架构演进逻辑。
