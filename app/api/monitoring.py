from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.security import get_request_context
from app.db.models import (
    Conversation,
    Document,
    KnowledgeBase,
    KnowledgeChunk,
    KnowledgeTask,
    Message,
    ToolCall,
)
from app.db.session import get_db
from app.schemas.context import RequestContext


router = APIRouter()


def count_rows(db: Session, model, *conditions) -> int:
    return int(db.scalar(select(func.count()).select_from(model).where(*conditions)) or 0)


def read_recent_log_lines(limit: int) -> list[str]:
    log_file = Path("logs") / "agent.log"

    if not log_file.exists():
        return []

    lines = log_file.read_text(encoding="utf-8", errors="replace").splitlines()
    return lines[-limit:]


@router.get("/overview")
def monitoring_overview(
    context: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
) -> dict:
    tool_status_rows = db.execute(
        select(ToolCall.status, func.count(ToolCall.id))
        .where(
            ToolCall.tenant_id == context.tenant_id,
            ToolCall.user_id == context.user_id,
        )
        .group_by(ToolCall.status)
    ).all()

    recent_tool_rows = db.execute(
        select(
            ToolCall.id,
            ToolCall.tool_name,
            ToolCall.status,
            ToolCall.latency_ms,
            ToolCall.created_at,
        )
        .where(
            ToolCall.tenant_id == context.tenant_id,
            ToolCall.user_id == context.user_id,
        )
        .order_by(ToolCall.created_at.desc())
        .limit(8)
    ).all()

    return {
        "context": {
            "request_id": context.request_id,
            "tenant_id": context.tenant_id,
            "user_id": context.user_id,
            "knowledge_base_id": context.knowledge_base_id,
        },
        "counts": {
            "conversations": count_rows(
                db,
                Conversation,
                Conversation.tenant_id == context.tenant_id,
                Conversation.user_id == context.user_id,
            ),
            "messages": count_rows(
                db,
                Message,
                Message.tenant_id == context.tenant_id,
                Message.user_id == context.user_id,
            ),
            "knowledge_bases": count_rows(
                db,
                KnowledgeBase,
                KnowledgeBase.tenant_id == context.tenant_id,
            ),
            "documents": count_rows(
                db,
                Document,
                Document.tenant_id == context.tenant_id,
            ),
            "chunks": count_rows(
                db,
                KnowledgeChunk,
                KnowledgeChunk.tenant_id == context.tenant_id,
            ),
            "knowledge_tasks": count_rows(
                db,
                KnowledgeTask,
                KnowledgeTask.tenant_id == context.tenant_id,
                KnowledgeTask.user_id == context.user_id,
            ),
            "tool_calls": count_rows(
                db,
                ToolCall,
                ToolCall.tenant_id == context.tenant_id,
                ToolCall.user_id == context.user_id,
            ),
        },
        "tool_status": {
            status or "unknown": total for status, total in tool_status_rows
        },
        "recent_tools": [
            {
                "id": row.id,
                "tool_name": row.tool_name,
                "status": row.status,
                "latency_ms": row.latency_ms,
                "created_at": row.created_at.isoformat(),
            }
            for row in recent_tool_rows
        ],
    }


@router.get("/logs")
def recent_logs(
    limit: int = Query(default=80, ge=1, le=300),
) -> dict:
    return {
        "lines": read_recent_log_lines(limit),
    }
