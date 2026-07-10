from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import get_request_context, require_permission
from app.db.session import get_db
from app.schemas.context import RequestContext
from app.schemas.conversation import ConversationDetailResponse,ConversationListResponse
from app.services.conversation_service import ConversationService


router = APIRouter()

conversation_service = ConversationService()

@router.get(
    "",
    response_model=ConversationListResponse,
)
def list_conversations(
    limit: int = 20,
    offset: int = 0,
    context: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
) -> ConversationListResponse:
    require_permission(context, "conversation:read")
    return conversation_service.list_conversations(
        db=db,
        context=context,
        limit=limit,
        offset=offset,
    )

@router.get(
    "/{conversation_id}",
    response_model=ConversationDetailResponse,
)
def get_conversation(
    conversation_id: str,
    context: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
) -> ConversationDetailResponse:
    require_permission(context, "conversation:read")
    conversation = conversation_service.get_conversation_detail(
        db=db,
        context=context,
        conversation_id=conversation_id,
    )

    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="会话不存在或无权访问",
        )

    return conversation