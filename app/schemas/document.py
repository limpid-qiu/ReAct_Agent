from datetime import datetime

from pydantic import BaseModel, Field


class DocumentListItem(BaseModel):
    id: str = Field(..., description="文档 ID")
    file_name: str = Field(..., description="文件名")
    file_path: str = Field(..., description="文件路径")
    file_hash: str = Field(..., description="文件 hash")
    status: str = Field(..., description="入库状态")
    chunk_count: int = Field(..., description="切片数量")
    error: str | None = Field(default=None, description="错误信息")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")
    indexed_at: datetime | None = Field(default=None, description="入库完成时间")


class DocumentListResponse(BaseModel):
    documents: list[DocumentListItem] = Field(default_factory=list)


class DocumentVersionItem(BaseModel):
    id: str = Field(..., description="文档版本 ID")
    document_id: str = Field(..., description="文档 ID")
    version: int = Field(..., description="版本号")
    file_name: str = Field(..., description="文件名")
    file_path: str = Field(..., description="文件路径")
    file_hash: str = Field(..., description="文件 hash")
    status: str = Field(..., description="版本状态")
    is_active: bool = Field(..., description="是否为当前生效版本")
    chunk_count: int = Field(..., description="切片数量")
    error: str | None = Field(default=None, description="错误信息")
    created_by: str = Field(..., description="创建用户")
    created_at: datetime = Field(..., description="创建时间")
    parsed_at: datetime | None = Field(default=None, description="解析完成时间")
    indexed_at: datetime | None = Field(default=None, description="索引完成时间")


class DocumentVersionListResponse(BaseModel):
    versions: list[DocumentVersionItem] = Field(default_factory=list)


class KnowledgeChunkItem(BaseModel):
    id: str = Field(..., description="Chunk ID")
    tenant_id: str = Field(..., description="租户 ID")
    knowledge_base_id: str = Field(..., description="知识库 ID")
    document_id: str = Field(..., description="文档 ID")
    document_version_id: str = Field(..., description="文档版本 ID")
    chunk_index: int = Field(..., description="切片序号")
    chunk_hash: str = Field(..., description="切片 hash")
    content: str = Field(..., description="切片内容")
    source: str | None = Field(default=None, description="来源文件")
    page: str | None = Field(default=None, description="页码")
    vector_id: str | None = Field(default=None, description="向量库 ID")
    metadata: dict | None = Field(default=None, description="扩展元数据")
    status: str = Field(..., description="Chunk 状态")
    created_at: datetime = Field(..., description="创建时间")


class KnowledgeChunkListResponse(BaseModel):
    chunks: list[KnowledgeChunkItem] = Field(default_factory=list)


class DocumentDetailResponse(BaseModel):
    document: DocumentListItem = Field(..., description="文档信息")
    active_version: DocumentVersionItem | None = Field(
        default=None,
        description="当前生效版本",
    )

class DocumentUploadResponse(BaseModel):
    document_id: str = Field(..., description="文档 ID")
    document_version_id: str = Field(..., description="文档版本 ID")
    task_id: str = Field(..., description="知识库任务 ID")
    status: str = Field(..., description="任务状态")
    message: str = Field(..., description="提示信息")

