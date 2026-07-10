# Phase 4 Tool Inventory

## 1. Current Tool Loading Flow

The current Agent tool flow is:

```text
API request
  -> AgentService.chat / AgentService.chat_stream
  -> set_current_request_context(context)
  -> ReActAgent.execute_stream(...)
  -> LangChain create_agent(...)
  -> tools declared in agent/tools/agent_tools.py
  -> middleware.monitor_tool wraps tool execution
```

Key files:

- `agent/react_agent.py`: directly passes tool objects into `create_agent`.
- `agent/tools/agent_tools.py`: defines tools with LangChain `@tool`.
- `agent/tools/middleware.py`: logs tool call name and raw args, then delegates execution.
- `app/services/agent_service.py`: sets request context before Agent execution.
- `app/schemas/context.py`: provides `request_id`, `user_id`, `tenant_id`, `knowledge_base_id`, `roles`, and `permissions`.

## 2. Registered Tools

| Tool | Input | Output | External dependency | Side effect | Current risk |
| --- | --- | --- | --- | --- | --- |
| `rag_summarize` | `query: str` | RAG answer string with citations | Chroma / local vector store, LLM | Reads tenant knowledge base | Relies on request context, but has no explicit tool permission check |
| `get_weather` | `city: str` | Weather text | AMap HTTP API, `AMAP_KEY` | External HTTP call | No API key availability check, no structured fallback, error may return `None` |
| `get_user_id` | none | Random user id string | Local hardcoded list | None | Demo behavior, not bound to authenticated request user |
| `get_current_month` | none | `YYYY-MM` string | System time | None | Low risk |
| `fetch_external_data` | `user_id: str`, `month: str` | Usage record dict or empty string | Local CSV file | Reads local data file into process memory | No permission check that requested `user_id` matches current user or tenant |
| `fill_context_for_report` | none | Static confirmation string | LangGraph runtime context via middleware | Sets `runtime.context["report"] = True` in middleware | The required call order is prompt-enforced only, not code-enforced |

## 3. Prompt Tool Consistency

`prompts/main_prompt.txt` now only lists tools that are implemented in `agent/tools/agent_tools.py` and registered in `agent/react_agent.py`.

Resolved item:

- Removed the previously prompt-declared but unimplemented `get_user_location` tool from `prompts/main_prompt.txt`.

## 4. Current Governance Capabilities

Already present:

- `monitor_tool` middleware wraps all tool calls.
- Tool name and raw input args are logged.
- Tool success and failure are logged.
- Request context is available through `ContextVar`.
- `RequestContext` already includes fields needed for future RBAC: `roles` and `permissions`.
- `rag_summarize` passes `RequestContext` into RAG, so tenant / knowledge base filtering can happen in retrieval.

Missing:

- No Tool Registry.
- No per-tool metadata such as timeout, retry policy, permission, enabled flag, or audit flag.
- No explicit tool-level permission check.
- No input schema governance beyond LangChain function signatures.
- No parameter sanitization or sensitive field redaction.
- No persistent tool audit table.
- No structured tool call result model.
- No unified timeout wrapper for all tools.
- No retry or fallback strategy.
- No idempotency protection for tools with future side effects.

## 5. Current Risk Points

### Permission Boundary

`fetch_external_data(user_id, month)` accepts any `user_id` generated or supplied by the Agent. It does not verify that the requested `user_id` belongs to the authenticated request context.

`rag_summarize(query)` uses request context for retrieval filtering, but the tool itself is callable by any Agent run that includes it.

### Audit Boundary

Tool calls are logged but not persisted in a queryable audit table. Logs also include raw tool args, which may become unsafe once tools accept sensitive fields.

### Reliability Boundary

`get_weather` has HTTP timeout settings inside the tool, but other tools do not have unified timeout handling. Exceptions are logged by middleware and then re-raised.

### Prompt-Enforced Workflow

Report generation order depends mainly on prompt instructions:

```text
get_user_id -> get_current_month -> fill_context_for_report -> fetch_external_data
```

The code only changes dynamic prompt behavior after `fill_context_for_report`; it does not prevent `fetch_external_data` from being called before that tool.

## 6. Recommended Next Step

Proceed to Tool Registry design.

The first version should introduce a central registry that declares:

- tool name
- description
- input schema
- permission requirement
- timeout
- retry policy
- enabled flag
- audit flag
- sensitivity level

Then `ReActAgent` should load tools from the registry instead of hardcoding the list directly in `agent/react_agent.py`.

