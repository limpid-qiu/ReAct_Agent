from prometheus_client import Counter, Histogram


HTTP_REQUESTS_TOTAL = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "path", "status"],
)

HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "path"],
)

TOOL_CALLS_TOTAL = Counter(
    "tool_calls_total",
    "Total tool calls",
    ["tool_name", "status"],
)

TOOL_CALL_DURATION_SECONDS = Histogram(
    "tool_call_duration_seconds",
    "Tool call duration in seconds",
    ["tool_name"],
)

RAG_RETRIEVAL_TOTAL = Counter(
    "rag_retrieval_total",
    "Total RAG retrieval calls",
    ["status"],
)

RAG_RETRIEVAL_DURATION_SECONDS = Histogram(
    "rag_retrieval_duration_seconds",
    "RAG retrieval duration in seconds",
)

MODEL_CALLS_TOTAL = Counter(
    "model_calls_total",
    "Total model calls",
    ["status"],
)

MODEL_CALL_DURATION_SECONDS = Histogram(
    "model_call_duration_seconds",
    "Model call duration in seconds",
)