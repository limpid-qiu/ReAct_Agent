from sqlalchemy.orm import Session

from app.db.models import ToolCall
from app.schemas.context import RequestContext


class ToolAuditService:
    def record_tool_call(
        self,
        db: Session,
        context: RequestContext | None,
        tool_name: str,
        input_summary: dict | None,
        output_summary: str | None,
        status: str,
        latency_ms: int | None = None,
        error_message: str | None = None,
    ) -> ToolCall:
        record = ToolCall(
            request_id=context.request_id if context else None,
            conversation_id=context.conversation_id if context else None,
            tenant_id=context.tenant_id if context else None,
            user_id=context.user_id if context else None,
            tool_name=tool_name,
            input_summary=input_summary,
            output_summary=output_summary,
            status=status,
            latency_ms=latency_ms,
            error_message=error_message,
        )

        db.add(record)
        db.commit()
        db.refresh(record)

        return record