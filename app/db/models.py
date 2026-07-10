from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, Index, JSON, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


def generate_conversation_id() -> str:
    return f"conv_{uuid4().hex}"

def generate_message_id() -> str:
    return f"msg_{uuid4().hex}"

def generate_document_id() -> str:
    return f"doc_{uuid4().hex}"

def generate_knowledge_base_id() -> str:
    return f"kb_{uuid4().hex}"

def generate_document_version_id() -> str:
    return f"docver_{uuid4().hex}"

def generate_chunk_id() -> str:
    return f"chunk_{uuid4().hex}"

def generate_tool_call_id() -> str:
    return f"toolcall_{uuid4().hex}"


class Conversation(Base):
    """
    会话表。

    一条 conversation 属于某个 tenant 下的某个 user。
    """

    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(
        String(64),
        primary_key=True,
        default=generate_conversation_id,
    )

    tenant_id: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        index=True,
    )

    user_id: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        index=True,
    )

    title: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    messages: Mapped[list["Message"]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
    )

class Message(Base):
    """
    消息表。

    role 建议值：
    - user
    - assistant
    - system
    - tool
    """

    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(
        String(64),
        primary_key=True,
        default=generate_message_id,
    )

    conversation_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    tenant_id: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        index=True,
    )

    user_id: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        index=True,
    )

    role: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )

    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
        index=True,
    )

    conversation: Mapped[Conversation] = relationship(
        back_populates="messages",
    )

def generate_task_id() -> str:
    return f"task_{uuid4().hex}"

class KnowledgeTask(Base):
    """
    知识库任务表。

    用于记录文档解析、Embedding、向量入库、知识库重建等长任务状态。
    """

    __tablename__ = "knowledge_tasks"

    id: Mapped[str] = mapped_column(
        String(64),
        primary_key=True,
        default=generate_task_id,
    )

    tenant_id: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        index=True,
    )

    user_id: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        index=True,
    )

    knowledge_base_id: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        index=True,
    )

    task_type: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )

    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="pending",
        index=True,
    )

    progress: Mapped[int] = mapped_column(
        default=0,
        nullable=False,
    )

    message: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    result: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
    )

    error: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

class KnowledgeBase(Base):
    """
    知识库表。

    第三阶段新增：
    用于显式管理 tenant 下的多个知识库，而不是只依赖请求头里的
    knowledge_base_id 字符串。
    """

    __tablename__ = "knowledge_bases"

    id: Mapped[str] = mapped_column(
        String(64),
        primary_key=True,
        default=generate_knowledge_base_id,
    )

    tenant_id: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        index=True,
    )

    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    created_by: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        index=True,
    )

    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="active",
        index=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

class DocumentVersion(Base):
    """
    文档版本表。

    一个 Document 可以有多个版本。
    每次文件内容变化后创建新版本，支持增量更新、回滚和审计。
    """

    __tablename__ = "document_versions"

    id: Mapped[str] = mapped_column(
        String(64),
        primary_key=True,
        default=generate_document_version_id,
    )

    document_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    tenant_id: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        index=True,
    )

    knowledge_base_id: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        index=True,
    )

    version: Mapped[int] = mapped_column(
        nullable=False,
        default=1,
    )

    file_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    file_path: Mapped[str] = mapped_column(
        String(1024),
        nullable=False,
    )

    file_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )

    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="pending",
        index=True,
    )

    is_active: Mapped[bool] = mapped_column(
        default=False,
        nullable=False,
        index=True,
    )

    chunk_count: Mapped[int] = mapped_column(
        default=0,
        nullable=False,
    )

    error: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    created_by: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        index=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    parsed_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    indexed_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    document: Mapped["Document"] = relationship(
        back_populates="versions",
    )

class KnowledgeChunk(Base):
    """
    知识库 chunk 表。

    用于记录每个文本切片与向量库中的 vector_id 的映射关系。
    这样后续才能支持引用来源、版本回滚、增量删除和检索评估。
    """

    __tablename__ = "knowledge_chunks"

    id: Mapped[str] = mapped_column(
        String(64),
        primary_key=True,
        default=generate_chunk_id,
    )

    tenant_id: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        index=True,
    )

    knowledge_base_id: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        index=True,
    )

    document_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    document_version_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("document_versions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    chunk_index: Mapped[int] = mapped_column(
        nullable=False,
    )

    chunk_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )

    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    source: Mapped[str | None] = mapped_column(
        String(1024),
        nullable=True,
    )

    page: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )

    vector_id: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
        index=True,
    )

    metadata_: Mapped[dict | None] = mapped_column(
        "metadata",
        JSON,
        nullable=True,
    )

    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="active",
        index=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

class Document(Base):
    """
    文档表。

    用数据库替代 md5.txt，记录每个租户、每个知识库下的文件入库状态。
    """

    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(
        String(64),
        primary_key=True,
        default=generate_document_id,
    )

    tenant_id: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        index=True,
    )

    user_id: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        index=True,
    )

    knowledge_base_id: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        index=True,
    )

    file_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    file_path: Mapped[str] = mapped_column(
        String(1024),
        nullable=False,
    )

    file_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )

    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="pending",
        index=True,
    )

    chunk_count: Mapped[int] = mapped_column(
        default=0,
        nullable=False,
    )

    error: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    indexed_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    versions: Mapped[list["DocumentVersion"]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
    )

class ToolCall(Base):
    """
    工具调用审计表。

    用于记录 Agent 每次工具调用，支持审计、排障、权限追踪和后续指标统计。
    """

    __tablename__ = "tool_calls"

    id: Mapped[str] = mapped_column(
        String(64),
        primary_key=True,
        default=generate_tool_call_id,
    )

    request_id: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
        index=True,
    )

    conversation_id: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        index=True,
    )

    tenant_id: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
        index=True,
    )

    user_id: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
        index=True,
    )

    tool_name: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        index=True,
    )

    input_summary: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
    )

    output_summary: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        index=True,
    )

    latency_ms: Mapped[int | None] = mapped_column(
        nullable=True,
    )

    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
        index=True,
    )

Index(
    "idx_conversation_tenant_user",
    Conversation.tenant_id,
    Conversation.user_id,
)

Index(
    "idx_message_conversation_created",
    Message.conversation_id,
    Message.created_at,
)

Index(
    "idx_knowledge_task_tenant_user",
    KnowledgeTask.tenant_id,
    KnowledgeTask.user_id,
    KnowledgeTask.created_at,
)

Index(
    "idx_document_tenant_kb_hash",
    Document.tenant_id,
    Document.knowledge_base_id,
    Document.file_hash,
)

Index(
    "idx_document_tenant_kb_status",
    Document.tenant_id,
    Document.knowledge_base_id,
    Document.status,
)

Index(
    "idx_knowledge_base_tenant_status",
    KnowledgeBase.tenant_id,
    KnowledgeBase.status,
)

Index(
    "idx_document_version_document_active",
    DocumentVersion.document_id,
    DocumentVersion.is_active,
)

Index(
    "idx_document_version_tenant_kb_hash",
    DocumentVersion.tenant_id,
    DocumentVersion.knowledge_base_id,
    DocumentVersion.file_hash,
)

Index(
    "idx_chunk_tenant_kb_document",
    KnowledgeChunk.tenant_id,
    KnowledgeChunk.knowledge_base_id,
    KnowledgeChunk.document_id,
)

Index(
    "idx_chunk_document_version_status",
    KnowledgeChunk.document_version_id,
    KnowledgeChunk.status,
)

Index(
    "idx_tool_call_tenant_user_created",
    ToolCall.tenant_id,
    ToolCall.user_id,
    ToolCall.created_at,
)

Index(
    "idx_tool_call_request_tool",
    ToolCall.request_id,
    ToolCall.tool_name,
)
