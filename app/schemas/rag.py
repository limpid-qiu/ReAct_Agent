from pydantic import BaseModel, Field


class RagSearchRequest(BaseModel):
    query: str = Field(..., description="检索问题")


class RagCitation(BaseModel):
    chunk_id: str | None = Field(default=None, description="Chunk ID")
    document_id: str | None = Field(default=None, description="文档 ID")
    document_version_id: str | None = Field(default=None, description="文档版本 ID")
    source: str | None = Field(default=None, description="来源文件")
    page: str | None = Field(default=None, description="页码")
    chunk_index: int | None = Field(default=None, description="切片序号")


class RagRetrievedChunk(BaseModel):
    content: str = Field(..., description="命中的 chunk 内容")
    metadata: dict = Field(default_factory=dict, description="Chunk 元数据")


class RagAnswerResponse(BaseModel):
    answer: str = Field(..., description="RAG 生成答案")
    citations: list[RagCitation] = Field(default_factory=list, description="引用来源")
    retrieved_chunks: list[RagRetrievedChunk] = Field(
        default_factory=list,
        description="检索命中的 chunk",
    )
