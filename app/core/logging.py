import logging
import sys
from pathlib import Path


class RequestContextLogFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        for field in (
            "request_id",
            "tenant_id",
            "user_id",
            "conversation_id",
            "knowledge_base_id",
            "request_latency_ms",
            "agent_latency_ms",
            "latency_ms",
            "message_count",
            "output_length",
            "hit_count",
            "query",
            "document_ids",
            "chunk_ids",
            "sources",
            "tool_name",
            "status",
            "file_name",
            "file_size",
            "file_hash",
            "document_id",
            "document_version_id",
            "task_id",
            "matched_patterns",
        ):
            if not hasattr(record, field):
                setattr(record, field, "-")

        return True

def setup_logging(debug: bool = False) -> None:
    """
    初始化应用日志配置。

    当前版本使用 Python 标准 logging。

    作用：
    - 统一日志格式。
    - 控制日志级别。
    - 将日志输出到控制台。
    - 后续可以扩展为 JSON 日志，方便接入 ELK / Loki。

    参数：
    - debug=True：输出 DEBUG 级别日志。
    - debug=False：输出 INFO 级别日志。
    """

    log_level = logging.DEBUG if debug else logging.INFO

    log_dir = Path("logs")
    log_dir.mkdir(parents=True, exist_ok=True)

    formatter = logging.Formatter(
        "%(asctime)s | "
        "%(levelname)s | "
        "%(name)s | "
        "request_id=%(request_id)s | "
        "tenant_id=%(tenant_id)s | "
        "user_id=%(user_id)s | "
        "conversation_id=%(conversation_id)s | "
        "knowledge_base_id=%(knowledge_base_id)s | "
        "request_latency_ms=%(request_latency_ms)s | "
        "agent_latency_ms=%(agent_latency_ms)s | "
        "latency_ms=%(latency_ms)s | "
        "message_count=%(message_count)s | "
        "output_length=%(output_length)s | "
        "hit_count=%(hit_count)s | "
        "query=%(query)s | "
        "document_ids=%(document_ids)s | "
        "chunk_ids=%(chunk_ids)s | "
        "sources=%(sources)s | "
        "tool_name=%(tool_name)s | "
        "status=%(status)s | "
        "file_name=%(file_name)s | "
        "file_size=%(file_size)s | "
        "file_hash=%(file_hash)s | "
        "document_id=%(document_id)s | "
        "document_version_id=%(document_version_id)s | "
        "task_id=%(task_id)s | "
        "matched_patterns=%(matched_patterns)s | "
        "%(message)s"
    )

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.addFilter(RequestContextLogFilter())
    console_handler.setFormatter(formatter)

    file_handler = logging.FileHandler(
        log_dir / "agent.log",
        encoding="utf-8",
    )
    file_handler.addFilter(RequestContextLogFilter())
    file_handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    root_logger.handlers.clear()
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)


def get_logger(name: str) -> logging.Logger:
    """
    获取指定名称的 logger。

    使用方式：
    logger = get_logger(__name__)

    好处：
    - 每个模块都有自己的 logger 名称。
    - 出问题时能看出日志来自哪个文件。
    """

    return logging.getLogger(name)

