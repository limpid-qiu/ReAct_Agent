from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.db.models import Conversation, Message
from app.schemas.chat import ChatMessage
from app.schemas.context import RequestContext
from app.schemas.conversation import (
    ConversationDetailResponse,
    ConversationListItem,
    ConversationListResponse,
    MessageItem,
)

def build_conversation_title(
    content: str,
    max_length: int = 30,
) -> str:
    """
    根据用户首条消息生成会话标题。

    当前阶段使用规则生成：
    - 去掉首尾空白。
    - 把连续空白压成一个空格。
    - 超过 max_length 则截断。
    """

    title = " ".join(content.strip().split())

    if not title:
        return "新会话"

    if len(title) <= max_length:
        return title

    return title[:max_length] + "..."

class ConversationService:
    """
    会话服务。

    第二阶段：
    - 使用数据库保存会话与消息。
    - 按 tenant_id / user_id / conversation_id 隔离访问。
    """

    def get_or_create_conversation(
        self,
        db: Session,
        context: RequestContext,
        first_message: str | None = None,
    ) -> Conversation:
        """
        获取或创建会话。

        如果 context.conversation_id 存在，则只能查当前 tenant/user 下的会话。
        查不到则创建一个新会话。
        """

        if context.conversation_id:
            conversation = db.scalar(
                select(Conversation).where(
                    Conversation.id == context.conversation_id,
                    Conversation.tenant_id == context.tenant_id,
                    Conversation.user_id == context.user_id,
                )
            )

            if conversation:
                return conversation

        conversation = Conversation(
            id=context.conversation_id,
            tenant_id=context.tenant_id,
            user_id=context.user_id,
            title=build_conversation_title(first_message or ""),
        )

        db.add(conversation)
        db.commit()
        db.refresh(conversation)

        return conversation

    def get_history(
        self,
        db: Session,
        context: RequestContext,
        limit: int = 12,
    ) -> list[ChatMessage]:
        """
        获取最近 N 条历史消息。

        注意：
        - 数据库按时间倒序取最近 N 条。
        - 返回给 Agent 前恢复为正序。
        """

        if not context.conversation_id:
            return []

        messages = db.scalars(
            select(Message)
            .where(
                Message.conversation_id == context.conversation_id,
                Message.tenant_id == context.tenant_id,
                Message.user_id == context.user_id,
            )
            .order_by(Message.created_at.desc())
            .limit(limit)
        ).all()

        return [
            ChatMessage(role=message.role, content=message.content)
            for message in reversed(messages)
        ]

    def save_user_message(
        self,
        db: Session,
        context: RequestContext,
        content: str,
    ) -> Message:
        return self._save_message(
            db=db,
            context=context,
            role="user",
            content=content,
        )

    def save_assistant_message(
        self,
        db: Session,
        context: RequestContext,
        content: str,
    ) -> Message:
        return self._save_message(
            db=db,
            context=context,
            role="assistant",
            content=content,
        )

    def _save_message(
        self,
        db: Session,
        context: RequestContext,
        role: str,
        content: str,
    ) -> Message:
        if not context.conversation_id:
            raise ValueError("保存消息前必须先生成 conversation_id")

        message = Message(
            conversation_id=context.conversation_id,
            tenant_id=context.tenant_id,
            user_id=context.user_id,
            role=role,
            content=content,
        )

        db.add(message)
        db.commit()
        db.refresh(message)

        return message
    
    def get_conversation_detail(
        self,
        db: Session,
        context: RequestContext,
        conversation_id: str,
    ) -> ConversationDetailResponse | None:
        conversation = db.scalar(
            select(Conversation).where(
                Conversation.id == conversation_id,
                Conversation.tenant_id == context.tenant_id,
                Conversation.user_id == context.user_id,
            )
        )

        if not conversation:
            return None

        messages = db.scalars(
            select(Message)
            .where(
                Message.conversation_id == conversation.id,
                Message.tenant_id == context.tenant_id,
                Message.user_id == context.user_id,
            )
            .order_by(Message.created_at.asc())
        ).all()

        return ConversationDetailResponse(
            id=conversation.id,
            tenant_id=conversation.tenant_id,
            user_id=conversation.user_id,
            title=conversation.title,
            created_at=conversation.created_at,
            updated_at=conversation.updated_at,
            messages=[
                MessageItem(
                    id=message.id,
                    role=message.role,
                    content=message.content,
                    created_at=message.created_at,
                )
                for message in messages
            ],
        )
    
    def list_conversations(
        self,
        db: Session,
        context: RequestContext,
        limit: int = 20,
        offset: int = 0,
    ) -> ConversationListResponse:
        rows = db.execute(
            select(
                Conversation,
                func.count(Message.id).label("message_count"),
            )
            .outerjoin(Message, Message.conversation_id == Conversation.id)
            .where(
                Conversation.tenant_id == context.tenant_id,
                Conversation.user_id == context.user_id,
            )
            .group_by(Conversation.id)
            .order_by(Conversation.updated_at.desc())
            .offset(offset)
            .limit(limit)
        ).all()

        return ConversationListResponse(
            conversations=[
                ConversationListItem(
                    id=conversation.id,
                    title=conversation.title,
                    created_at=conversation.created_at,
                    updated_at=conversation.updated_at,
                    message_count=message_count,
                )
                for conversation, message_count in rows
            ]
        )