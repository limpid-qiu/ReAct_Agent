from time import perf_counter
from collections.abc import Generator

from sqlalchemy.orm import Session

from agent.react_agent import ReActAgent
from app.core.request_context import (
    reset_current_request_context,
    set_current_request_context,
)
from app.schemas.chat import ChatMessage
from app.schemas.context import RequestContext
from app.services.conversation_service import ConversationService
from app.core.logging import get_logger

from pydantic import BaseModel
from app.core.concurrency import model_concurrency_limiter



logger = get_logger(__name__)

class AgentChatResult(BaseModel):
    answer: str
    conversation_id: str

class AgentService:
    def __init__(self) -> None:
        self.agent = ReActAgent()
        self.conversation_service = ConversationService()

    @staticmethod
    def _convert_history(history: list[ChatMessage] | None) -> list[dict]:
        if not history:
            return []

        return [
            {
                "role": message.role,
                "content": message.content,
            }
            for message in history
        ]

    def chat(
        self,
        db: Session,
        query: str,
        context: RequestContext,
        history: list[ChatMessage] | None = None,
    ) -> AgentChatResult:
        request_started_at = perf_counter()
        conversation = self.conversation_service.get_or_create_conversation(
            db=db,
            context=context,
            first_message=query,
        )

        context = context.model_copy(
            update={
                "conversation_id": conversation.id,
            }
        )

        logger.info(
            "chat request started",
            extra=context.log_extra(),
        )

        db_history = self.conversation_service.get_history(
            db=db,
            context=context,
        )

        effective_history = db_history or history or []
        converted_history = self._convert_history(effective_history)

        self.conversation_service.save_user_message(
            db=db,
            context=context,
            content=query,
        )

        token = set_current_request_context(context)

        try:
            chunks: list[str] = []

            agent_started_at = perf_counter()

            with model_concurrency_limiter.acquire():
                for chunk in self.agent.execute_stream(
                    query=query,
                    history=converted_history,
                ):
                    chunks.append(chunk)

            agent_latency_ms = int((perf_counter() - agent_started_at) * 1000)

            answer = "".join(chunks).strip()

            self.conversation_service.save_assistant_message(
                db=db,
                context=context,
                content=answer,
            )

            logger.info(
                "chat request finished",
                extra={
                    **context.log_extra(),
                    "answer_length": len(answer),
                    "agent_latency_ms": agent_latency_ms,
                    "request_latency_ms": int((perf_counter() - request_started_at) * 1000),
                },
            )

            return AgentChatResult(
                answer=answer,
                conversation_id=conversation.id,
            )

        finally:
            reset_current_request_context(token)

    def chat_stream(
        self,
        db: Session,
        query: str,
        context: RequestContext,
        history: list[ChatMessage] | None = None,
    ) -> Generator[str, None, None]:
        request_started_at = perf_counter()
        conversation = self.conversation_service.get_or_create_conversation(
            db=db,
            context=context,
            first_message=query,
        )

        context = context.model_copy(
            update={
                "conversation_id": conversation.id,
            }
        )

        logger.info(
            "chat stream request started",
            extra=context.log_extra(),
        )

        db_history = self.conversation_service.get_history(
            db=db,
            context=context,
        )

        effective_history = db_history or history or []
        converted_history = self._convert_history(effective_history)

        self.conversation_service.save_user_message(
            db=db,
            context=context,
            content=query,
        )

        token = set_current_request_context(context)
        chunks: list[str] = []

        try:
            agent_started_at = perf_counter()

            with model_concurrency_limiter.acquire():
                for chunk in self.agent.execute_stream(
                    query=query,
                    history=converted_history,
                ):
                    chunks.append(chunk)
                    yield chunk

            agent_latency_ms = int((perf_counter() - agent_started_at) * 1000)

            answer = "".join(chunks).strip()

            self.conversation_service.save_assistant_message(
                db=db,
                context=context,
                content=answer,
            )

            logger.info(
                "chat stream request finished",
                extra={
                    **context.log_extra(),
                    "answer_length": len(answer),
                    "agent_latency_ms": agent_latency_ms,
                    "request_latency_ms": int((perf_counter() - request_started_at) * 1000),
                },
            )

        finally:
            reset_current_request_context(token)