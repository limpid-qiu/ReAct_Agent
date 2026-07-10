# 第三阶段 RAG 改造验证清单

本文档用于验证第三阶段企业级 RAG 改造链路：

```text
知识库 -> 文档上传 -> 入库任务 -> 版本/chunk 管理 -> 检索引用 -> 删除/回滚 -> 评估
```

## 1. 准备环境

复制环境变量模板：

```powershell
Copy-Item .env.example .env
```

按需修改 `.env`：

```text
DASHSCOPE_API_KEY=你的 DashScope Key
AMAP_KEY=你的高德 Key
API_KEY=本地开发可留空
```

安装依赖：

```powershell
pip install -r requirements.txt
```

启动服务：

```powershell
uvicorn app.main:app --reload
```

健康检查：

```powershell
curl http://127.0.0.1:8000/api/health
```

## 2. 请求头约定

后续请求建议统一带上：

```text
X-User-ID: user_001
X-Tenant-ID: tenant_001
X-Knowledge-Base-ID: default
```

如果没有传 `X-Knowledge-Base-ID`，系统会尝试解析或创建默认知识库。

## 3. 创建知识库

```powershell
curl -X POST http://127.0.0.1:8000/api/knowledge/bases `
  -H "Content-Type: application/json" `
  -H "X-User-ID: user_001" `
  -H "X-Tenant-ID: tenant_001" `
  -d "{\"name\":\"扫地机器人知识库\",\"description\":\"产品选购、维护保养、故障排查资料\"}"
```

查看知识库：

```powershell
curl http://127.0.0.1:8000/api/knowledge/bases `
  -H "X-User-ID: user_001" `
  -H "X-Tenant-ID: tenant_001"
```

## 4. 上传文档

```powershell
curl -X POST http://127.0.0.1:8000/api/knowledge/documents/upload `
  -H "X-User-ID: user_001" `
  -H "X-Tenant-ID: tenant_001" `
  -H "X-Knowledge-Base-ID: default" `
  -F "file=@data/选购指南.txt"
```

预期返回：

```json
{
  "document_id": "doc_xxx",
  "document_version_id": "docver_xxx",
  "task_id": "task_xxx",
  "status": "pending",
  "message": "文档上传成功，入库任务已创建"
}
```

## 5. 查看任务进度

```powershell
curl http://127.0.0.1:8000/api/knowledge/tasks/task_xxx `
  -H "X-User-ID: user_001" `
  -H "X-Tenant-ID: tenant_001" `
  -H "X-Knowledge-Base-ID: default"
```

入库任务进度应经过：

```text
10  校验文档版本
20  文档解析中
40  文档切片中
60  向量写入中
80  chunk 元数据写入中
90  文档版本激活中
100 文档入库完成
```

## 6. 查看文档、版本和 chunks

文档列表：

```powershell
curl http://127.0.0.1:8000/api/knowledge/documents `
  -H "X-User-ID: user_001" `
  -H "X-Tenant-ID: tenant_001" `
  -H "X-Knowledge-Base-ID: default"
```

文档详情：

```powershell
curl http://127.0.0.1:8000/api/knowledge/documents/doc_xxx `
  -H "X-User-ID: user_001" `
  -H "X-Tenant-ID: tenant_001" `
  -H "X-Knowledge-Base-ID: default"
```

版本列表：

```powershell
curl http://127.0.0.1:8000/api/knowledge/documents/doc_xxx/versions `
  -H "X-User-ID: user_001" `
  -H "X-Tenant-ID: tenant_001" `
  -H "X-Knowledge-Base-ID: default"
```

chunk 列表：

```powershell
curl http://127.0.0.1:8000/api/knowledge/documents/doc_xxx/chunks `
  -H "X-User-ID: user_001" `
  -H "X-Tenant-ID: tenant_001" `
  -H "X-Knowledge-Base-ID: default"
```

## 7. RAG Search 验证引用来源

```powershell
curl -X POST http://127.0.0.1:8000/api/knowledge/search `
  -H "Content-Type: application/json" `
  -H "X-User-ID: user_001" `
  -H "X-Tenant-ID: tenant_001" `
  -H "X-Knowledge-Base-ID: default" `
  -d "{\"query\":\"扫地机器人滤网多久更换一次？\"}"
```

重点检查：

- `answer` 是否基于知识库内容。
- `citations` 是否包含 `source / document_id / chunk_id`。
- `retrieved_chunks` 是否命中相关内容。

## 8. 删除文档

```powershell
curl -X DELETE http://127.0.0.1:8000/api/knowledge/documents/doc_xxx `
  -H "X-User-ID: user_001" `
  -H "X-Tenant-ID: tenant_001" `
  -H "X-Knowledge-Base-ID: default"
```

预期：

- 文档状态变为 `deleted`。
- 版本状态变为 `deleted`。
- chunks 状态变为 `deleted`。
- Chroma 中相关向量被删除。

## 9. 版本回滚

```powershell
curl -X POST http://127.0.0.1:8000/api/knowledge/documents/doc_xxx/versions/docver_xxx/rollback `
  -H "X-User-ID: user_001" `
  -H "X-Tenant-ID: tenant_001" `
  -H "X-Knowledge-Base-ID: default"
```

预期：

- 当前 active 版本失效。
- 目标版本变为 active。
- 目标版本 chunks 变为 active。
- 目标版本向量重新写入 Chroma。

## 10. 本地 RAG 评估脚本

准备问题文件：

```text
data/eval_queries.txt
```

每行一个问题，例如：

```text
扫地机器人滤网多久更换一次？
扫地机器人适合有宠物的家庭吗？
扫地机器人无法回充怎么办？
```

运行：

```powershell
python scripts/evaluate_rag.py `
  --input data/eval_queries.txt `
  --tenant-id tenant_001 `
  --knowledge-base-id default
```

输出 JSONL：

```powershell
python scripts/evaluate_rag.py `
  --input data/eval_queries.txt `
  --output data/rag_eval_results.jsonl `
  --tenant-id tenant_001 `
  --knowledge-base-id default
```

## 11. 验收标准

第三阶段当前改造至少应满足：

- 文档可以通过 API 上传，而不是只能扫描本地 `data` 目录。
- 上传后能创建 `document_ingest` 任务。
- 任务可以看到阶段性进度。
- 入库完成后能查到文档、版本、chunks。
- RAG Search 能返回 citations。
- 新版本激活时旧版本向量失效。
- 文档支持软删除。
- 文档版本支持回滚。
- 可以用本地脚本做轻量评估。

## 12. 验收记录

验收时间：

```text
2026-07-07
```

验收环境：

```text
本地 FastAPI 服务
SQLite: data/app.db
Chroma: chroma_db
tenant_id: tenant_phase3_001
user_id: user_phase3_001
knowledge_base_id: kb_fb6b6b976e4d48eba9edc2ac38f675d7
```

本次手动验收结果：

- 创建知识库：通过。
- 文档上传：通过。
- `document_ingest` 入库任务：通过，任务最终状态为 `success`，进度为 `100`。
- 文档、版本、chunks 查询：通过。
- RAG Search 引用来源：通过，返回 `citations` 和 `retrieved_chunks`。
- 文档软删除：通过，删除后对应向量不再被检索命中。
- 同一文档多版本：通过，同一文件名再次上传后复用原 `document_id`，创建新的 `document_version_id`。
- 版本回滚：通过，回滚后目标版本变为 active，原 active 版本失效。
- 回滚后检索验证：通过，第二版本专用内容在回滚到第一版本后不再命中。

本次验收过程中修复的实现缺口：

- `app/services/rag_service.py` 已将 `progress_callback` 透传给底层 `VectorStoreService.ingest_document_version()`，确保入库任务能展示阶段性进度。
- `app/services/document_service.py` 已补齐同名文档版本逻辑：同一 `tenant_id + knowledge_base_id + file_name` 下再次上传未删除文档时，复用原 `Document` 并创建新的 `DocumentVersion`，而不是每次创建新文档。

当前结论：

```text
Phase 3 RAG 企业级改造链路已完成手动验收，可以进入 Phase 4 工具治理验证。
```
