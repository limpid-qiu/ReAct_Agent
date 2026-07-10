# ReAct Agent 项目学习教程

这份文档用于帮助初学者循序渐进看懂当前项目，并逐步具备二次开发能力。

项目本质上是一个基于 FastAPI、LangChain ReAct Agent、RAG、Chroma、SQLAlchemy 的 AI Agent 服务。它已经包含聊天接口、会话持久化、工具调用、知识库检索、文档入库、权限控制、限流、日志、指标和工具审计等能力。

学习时不要一开始陷入所有细节。推荐先抓主链路，再拆模块。

## 1. 项目全局地图

项目目录可以先这样理解：

```text
app/                 FastAPI 后端服务
  main.py            应用入口，注册路由、中间件、监控
  api/               HTTP 接口层
  services/          业务逻辑层
  schemas/           请求和响应数据结构
  core/              配置、安全、日志、限流、指标等基础能力
  db/                数据库模型、连接和初始化

agent/               Agent 核心
  react_agent.py     ReAct Agent 封装
  tools/             工具函数、工具注册表、工具中间件

rag/                 RAG 知识库能力
  rag_service.py     检索、拼接上下文、生成答案
  vector_store.py    Chroma 向量库、文档切片和入库

model/               模型工厂
  factory.py         创建 chat_model 和 embedding_model

prompts/             提示词
config/              YAML 配置
data/                本地数据、SQLite、上传文件和测试资料
docs/                项目文档
scripts/             辅助脚本
utils/               通用工具函数
```

最重要的主线是：

```text
用户请求
 -> FastAPI API 层
 -> Service 业务层
 -> ReActAgent
 -> 大模型和工具
 -> RAG / 外部工具
 -> 返回答案
 -> 保存会话和审计记录
```

## 2. 一次聊天请求的完整链路

一次普通聊天请求从 `POST /api/chat/` 进入。

主链路如下：

```text
app/main.py
 -> 注册 chat 路由

app/api/chat.py
 -> 接收请求
 -> 解析 ChatRequest
 -> 解析 RequestContext
 -> 检查权限、限流、prompt injection 风险
 -> 调用 AgentService

app/services/agent_service.py
 -> 获取或创建会话
 -> 读取历史消息
 -> 保存用户消息
 -> 设置当前请求上下文
 -> 调用 ReActAgent
 -> 保存助手回答
 -> 返回 answer 和 conversation_id

agent/react_agent.py
 -> 构造 messages
 -> 调用 LangChain create_agent 创建的 Agent
 -> 流式返回模型输出
```

可以把职责压缩成一句话：

```text
main.py 管入口，chat.py 管接口，agent_service.py 管业务流程，react_agent.py 管 AI 执行。
```

建议优先阅读：

```text
app/main.py
app/api/chat.py
app/services/agent_service.py
agent/react_agent.py
```

## 3. FastAPI 接口层

接口层主要位于 `app/api/`。

以 `app/api/chat.py` 为例，一个接口通常包含：

```text
路由声明
请求体 schema
依赖注入
权限检查
输入安全检查
业务 service 调用
响应封装
异常处理
```

普通聊天接口大致是：

```python
@router.post("/", response_model=ChatResponse)
def chat(
    request: ChatRequest,
    context: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
) -> ChatResponse:
    require_permission(context, "chat:write")
    inspect_prompt_text(request.query)
    context = context.with_conversation_id(request.conversation_id)
    check_chat_rate_limit(context)
    result = agent_service.chat(...)
    return ChatResponse(...)
```

这里要重点理解 `Depends(...)`。它表示 FastAPI 会自动准备参数，例如：

```text
get_request_context 负责从请求头解析用户、租户、权限和知识库上下文。
get_db 负责提供数据库 session。
```

## 4. AgentService 业务编排层

`app/services/agent_service.py` 是聊天业务的调度层。

它不直接实现大模型逻辑，也不直接写复杂 SQL，而是协调：

```text
ReActAgent             AI 执行
ConversationService    会话和消息存取
RequestContext         用户、租户、知识库上下文
model_concurrency_limiter 模型并发保护
```

普通聊天流程：

```text
开始计时
 -> 获取或创建会话
 -> 写回 conversation_id
 -> 读取数据库历史消息
 -> 转换历史消息格式
 -> 保存用户问题
 -> 设置当前请求上下文
 -> 限制模型并发
 -> 调用 ReActAgent.execute_stream
 -> 收集 chunks
 -> 拼接 answer
 -> 保存助手回答
 -> 返回结果
 -> 清理当前请求上下文
```

这里最重要的点：

```text
AgentService 让一次 Agent 调用具备会话记忆、用户隔离、数据库落盘、并发保护和日志追踪。
```

## 5. ReActAgent 核心

核心文件是 `agent/react_agent.py`。

初始化时：

```python
self.agent = create_agent(
    model=chat_model,
    system_prompt=system_prompt,
    tools=get_enabled_tools(),
    middleware=[monitor_tool, log_before_model, log_after_model, report_prompt_switch],
)
```

可以理解为：

```text
Agent = 大模型 + 系统提示词 + 可用工具 + 运行中间件
```

其中：

```text
chat_model        来自 model/factory.py
system_prompt     来自 prompts/main_prompt.txt
tools             来自 agent/tools/registry.py
middleware        负责日志、审计、权限、动态提示词等治理能力
```

`build_messages()` 负责把历史对话和当前问题整理成模型需要的消息格式。

`execute_stream()` 负责调用 `self.agent.stream(...)`，并一段一段产出回答。

## 6. 工具系统

工具系统主要看三个文件：

```text
agent/tools/agent_tools.py
agent/tools/registry.py
agent/tools/middleware.py
```

职责拆分：

```text
agent_tools.py
定义工具具体怎么干活。

registry.py
登记工具元信息和治理规则。

middleware.py
在工具执行前后做权限、参数、审计、重试、fallback。
```

当前工具包括：

```text
rag_summarize            基于知识库问答
get_weather              查询天气
get_user_id              获取演示用户 ID
get_current_month        获取当前月份
fetch_external_data      读取外部用户月度记录
fill_context_for_report  标记进入报告生成场景
```

工具函数通过 `@tool` 暴露给 LangChain Agent。

`TOOL_REGISTRY` 记录每个工具的：

```text
工具名
工具函数
描述
入参 schema
超时时间
重试策略
权限点
是否审计
是否启用
敏感字段
失败兜底消息
是否有副作用
是否要求幂等
```

完整工具调用链：

```text
用户提问
 -> Agent 判断需要工具
 -> 调用某个 tool
 -> monitor_tool 接管
 -> 查注册表
 -> 检查权限
 -> 校验参数
 -> 执行工具
 -> 记录日志、指标、审计
 -> 工具结果返回给 Agent
 -> Agent 生成最终回答
```

## 7. 工具中间件

`agent/tools/middleware.py` 是工具治理的核心。

最重要的是：

```python
@wrap_tool_call
def monitor_tool(request, handler):
```

它会在工具真正执行前后做这些事：

```text
获取工具名和参数
检查工具是否注册
敏感字段脱敏
检查工具权限
校验参数类型和格式
检查工具调用顺序
检查幂等要求
执行工具并按策略重试
失败时返回 fallback 或抛错
记录日志
记录 Prometheus 指标
写入 tool_calls 审计表
```

`fill_context_for_report` 比较特殊。它执行后会设置：

```python
request.runtime.context["report"] = True
```

随后 `report_prompt_switch` 会切换到报告生成提示词。

这说明工具不仅能返回数据，也能改变 Agent 当前运行上下文。

## 8. RAG 查询链路

RAG 主文件：

```text
rag/rag_service.py
rag/vector_store.py
```

对 Agent 来说，RAG 是一个工具：

```text
rag_summarize
```

查询链路：

```text
Agent 调用 rag_summarize
 -> 获取当前 RequestContext
 -> RagSummarizeService.rag_summarize
 -> VectorStoreService.get_retriever
 -> Chroma 按 query + metadata filter 检索
 -> 返回相关 docs
 -> 拼接 rag_context
 -> 调用 RAG prompt + chat_model
 -> 返回答案和引用来源
```

RAG 检索必须带过滤条件：

```text
tenant_id
knowledge_base_id
status=active
```

这防止不同租户、不同知识库之间串数据。

RAG prompt 位于：

```text
prompts/rag_summarize.txt
```

它要求模型必须基于参考资料回答，不编造，不扩展问题范围。

## 9. 文档入库和知识库管理

知识库接口位于：

```text
app/api/knowledge.py
```

相关服务：

```text
app/services/rag_service.py
app/services/knowledge_base_service.py
app/services/document_service.py
rag/vector_store.py
```

文档上传入库链路：

```text
POST /api/knowledge/documents/upload
 -> 校验文件名、后缀、content-type、大小
 -> 保存文件到上传目录
 -> 创建 Document
 -> 创建 DocumentVersion
 -> 创建 document_ingest 任务
 -> 后台执行 run_document_ingest_task
 -> VectorStoreService.ingest_document_version
 -> 读取文件
 -> 切成 chunks
 -> 给 chunk 添加 metadata
 -> 写入 Chroma
 -> 写入 KnowledgeChunk 数据库记录
 -> 激活当前文档版本
 -> 停用旧版本并删除旧向量
 -> 标记任务成功
```

这里有两套存储：

```text
Chroma
负责向量检索。

数据库
负责文档、版本、chunk、任务、引用和审计管理。
```

文档相关关系：

```text
KnowledgeBase
  -> Document
      -> DocumentVersion
          -> KnowledgeChunk
              -> Chroma Vector
```

## 10. 数据库模型总览

核心文件：

```text
app/db/models.py
```

可以分成五组：

```text
聊天会话组
Conversation
Message

知识库组
KnowledgeBase

文档版本组
Document
DocumentVersion
KnowledgeChunk

任务组
KnowledgeTask

工具审计组
ToolCall
```

聊天关系：

```text
Conversation 1 -> N Message
```

知识库关系：

```text
KnowledgeBase 1 -> N Document
Document 1 -> N DocumentVersion
DocumentVersion 1 -> N KnowledgeChunk
KnowledgeChunk 1 -> 1 Chroma vector
```

`ToolCall` 用来记录 Agent 每次工具调用：

```text
谁调用的
调用了哪个工具
参数摘要是什么
成功还是失败
耗时多久
错误是什么
```

## 11. 安全、权限、限流和请求上下文

核心文件：

```text
app/core/security.py
app/schemas/context.py
app/core/request_context.py
app/core/rate_limit.py
app/core/prompt_guard.py
```

`RequestContext` 是每次请求的业务身份证：

```text
request_id
user_id
tenant_id
conversation_id
knowledge_base_id
client_ip
roles
permissions
```

`get_request_context()` 从请求头解析身份和权限。

`require_permission()` 检查接口权限，例如：

```text
chat:write
knowledge:read
knowledge:write
knowledge:delete
```

工具还有单独权限，例如：

```text
tool:rag_summarize
tool:get_weather
tool:fetch_external_data
```

`request_context.py` 使用 `ContextVar`，让工具和 RAG 在深层调用中也能拿到当前请求上下文。

`rate_limit.py` 使用内存滑动窗口限流，同时限制：

```text
用户级请求频率
租户级请求频率
```

`prompt_guard.py` 用于检测可疑 prompt injection 文本。目前策略是记录 warning，不是直接拒绝。

## 12. 日志、指标和可观测性

核心文件：

```text
app/core/logging.py
app/core/metrics.py
app/services/tool_audit_service.py
app/main.py
agent/tools/middleware.py
rag/rag_service.py
app/services/agent_service.py
```

项目通过三类信息排查问题：

```text
日志
适合排查某一次具体请求。

指标
适合观察整体趋势和性能。

审计
适合追踪重要行为，尤其是工具调用。
```

`request_id` 是串起整次请求日志的关键。

Prometheus 指标通过：

```text
GET /metrics
```

暴露。

当前指标包括：

```text
HTTP 请求次数和耗时
模型调用次数和耗时
工具调用次数和耗时
RAG 检索次数和耗时
```

工具调用还会写入数据库 `tool_calls` 表。

## 13. 推荐学习顺序

如果从零重新看，建议按这个顺序：

```text
1. app/main.py
2. app/api/chat.py
3. app/services/agent_service.py
4. agent/react_agent.py
5. agent/tools/agent_tools.py
6. agent/tools/registry.py
7. agent/tools/middleware.py
8. rag/rag_service.py
9. rag/vector_store.py
10. app/api/knowledge.py
11. app/services/document_service.py
12. app/db/models.py
13. app/core/security.py
14. app/core/rate_limit.py
15. app/core/logging.py
16. app/core/metrics.py
```

每看一个文件，只问三个问题：

```text
这个文件属于哪一层？
它接收什么输入？
它把结果交给谁？
```

不要一开始背所有字段和代码。先抓数据流，再补细节。

## 14. 推荐实践路线

看懂之后，建议按小任务练习：

```text
1. 修改 prompts/main_prompt.txt，调整 Agent 回答风格。
2. 新增一个简单 GET API，例如 /api/version。
3. 给 ChatResponse 增加 answer_length 字段。
4. 新增一个只读工具 get_robot_maintenance_tip。
5. 在 TOOL_REGISTRY 中注册新工具和权限。
6. 在 DEFAULT_DEMO_PERMISSIONS 中加入新工具权限。
7. 观察工具调用日志和 tool_calls 审计记录。
8. 修改 RAG 引用格式，只显示 source 和 page。
9. 给上传文件增加额外校验。
10. 写一个最小测试脚本验证工具函数。
```

最推荐的第一个开发任务是：

```text
新增一个只读工具 get_robot_maintenance_tip
```

因为它能完整练习：

```text
写工具函数
注册工具
设置权限
让 Agent 调用工具
观察日志和审计
```

## 15. 总结

这个项目可以看成三层能力叠加：

```text
第一层：Web 服务
FastAPI、API、Service、Schema、DB。

第二层：AI Agent
LangChain ReActAgent、模型、提示词、工具、中间件。

第三层：工程治理
RAG、权限、限流、日志、指标、审计、文档版本、任务系统。
```

最终你要形成的心智模型是：

```text
用户请求不是直接丢给大模型。
它会先变成带身份、租户、会话、知识库和权限的上下文。
然后由 Service 层组织历史和数据库状态。
再交给 Agent 执行。
Agent 可以调用受治理的工具。
RAG 也是工具之一。
整个过程被日志、指标和审计记录下来。
```

掌握这条主线后，再看任何一个文件都会容易很多。
