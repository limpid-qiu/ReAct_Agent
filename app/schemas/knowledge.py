from pydantic import BaseModel, Field


class KnowledgeFileInfo(BaseModel):
    """
    单个知识库文件信息。

    用于描述 data 目录下某个知识文件的处理状态。
    """

    name: str = Field(
        ...,
        description="文件名",
        examples=["扫地机器人100问.pdf"],
    )

    path: str = Field(
        ...,
        description="文件路径",
        examples=["data/扫地机器人100问.pdf"],
    )

    md5: str | None = Field(
        default=None,
        description="文件 MD5 值，用于判断文件内容是否变化",
    )

    status: str | None = Field(
        default=None,
        description="文件处理状态，例如 loaded、skipped、failed、empty",
        examples=["loaded"],
    )

    message: str | None = Field(
        default=None,
        description="文件处理结果说明",
        examples=["文件已加载"],
    )

    chunks: int = Field(
        default=0,
        description="文件切分后的 chunk 数量",
    )


class KnowledgeRebuildResponse(BaseModel):
    """
    知识库重建响应。

    VectorStoreService.load_document() 当前会返回一个 stats 字典，
    这里用 Pydantic 模型把它规范化。
    """

    scanned: int = Field(
        default=0,
        description="扫描到的文件数量",
    )

    loaded: int = Field(
        default=0,
        description="本次成功加载的文件数量",
    )

    skipped: int = Field(
        default=0,
        description="跳过的文件数量，通常表示文件已入库",
    )

    failed: int = Field(
        default=0,
        description="加载失败的文件数量",
    )

    empty: int = Field(
        default=0,
        description="空文件或切分后无内容的文件数量",
    )

    chunks: int = Field(
        default=0,
        description="本次新增的 chunk 总数",
    )

    files: list[KnowledgeFileInfo] = Field(
        default_factory=list,
        description="每个文件的处理详情",
    )


class KnowledgePendingFilesResponse(BaseModel):
    """
    待入库文件响应。

    用于查看当前 data 目录下有哪些文件还没有被加载进向量库。
    """

    files: list[KnowledgeFileInfo] = Field(
        default_factory=list,
        description="待加载的知识库文件列表",
    )

    total: int = Field(
        default=0,
        description="待加载文件总数",
    )