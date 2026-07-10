# Phase 4 Tool Registry Design

## 1. Goal

The first Tool Registry version moves tool declaration out of `ReActAgent` and into a central registry.

This makes tool loading explicit and prepares the codebase for:

- tool-level permission checks
- parameter validation
- timeout and retry handling
- audit logging
- tenant-level enable / disable rules
- sensitive field masking

## 2. Current Implementation

Implemented file:

- `agent/tools/registry.py`

Updated file:

- `agent/react_agent.py`

`ReActAgent` now calls:

```python
tools=get_enabled_tools()
```

instead of hardcoding tool imports and a tool list inside the Agent constructor.

## 3. Registry Schema

Each tool is represented by `ToolDefinition`.

```text
tool_name
tool
description
input_schema
timeout_seconds
retry_policy
permission
audit_enabled
enabled
sensitive_fields
```

The retry policy is represented by:

```text
max_attempts
backoff_seconds
```

## 4. Registered Tool Metadata

| Tool | Permission | Timeout | Retry | Audit | Sensitive fields |
| --- | --- | --- | --- | --- | --- |
| `rag_summarize` | `tool:rag_summarize` | 30s | 1 attempt | yes | none |
| `get_weather` | `tool:get_weather` | 20s | 2 attempts | yes | none |
| `get_user_id` | `tool:get_user_id` | 5s | 1 attempt | yes | none |
| `get_current_month` | `tool:get_current_month` | 5s | 1 attempt | no | none |
| `fetch_external_data` | `tool:fetch_external_data` | 10s | 1 attempt | yes | `user_id` |
| `fill_context_for_report` | `tool:fill_context_for_report` | 5s | 1 attempt | yes | none |

## 5. Scope of This Step

This step only centralizes metadata and tool loading.

It does not yet enforce:

- permission checks
- timeout execution
- retry execution
- persistent audit logs
- schema validation beyond the existing LangChain tool signature
- tenant-level tool enablement

Those should be added through a dedicated Tool Executor / middleware upgrade in the next step.

## 6. Recommended Next Step

Add a permission check in the tool middleware:

```text
monitor_tool
  -> find ToolDefinition by tool name
  -> check definition.enabled
  -> check definition.permission in RequestContext.permissions
  -> redact sensitive args before logging
  -> call handler
```

For local demo compatibility, the first implementation can support a permissive mode:

```text
If RequestContext.permissions is empty, allow current tools.
If permissions are provided, enforce the declared permission.
```
