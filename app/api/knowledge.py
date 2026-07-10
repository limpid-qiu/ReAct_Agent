import hashlib
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.core.config import get_settings

from app.core.security import get_request_context, require_permission
from app.db.session import SessionLocal, get_db
from app.schemas.context import RequestContext
from app.schemas.common import SuccessResponse
from app.schemas.rag import RagAnswerResponse, RagSearchRequest
from app.schemas.document import (
    DocumentDetailResponse,
    DocumentListResponse,
    DocumentUploadResponse,
    DocumentVersionListResponse,
    KnowledgeChunkListResponse,
)
from app.schemas.task import (
    KnowledgeTaskDetailResponse,
    KnowledgeTaskListResponse,
    KnowledgeTaskSubmitResponse,
)
from app.services.document_service import DocumentService
from app.services.rag_service import RagService
from app.services.task_service import TaskService

from app.schemas.knowledge_base import (
    KnowledgeBaseCreateRequest,
    KnowledgeBaseCreateResponse,
    KnowledgeBaseListResponse,
)
from app.services.knowledge_base_service import KnowledgeBaseService

from app.core.logging import get_logger


# 创建知识库路由对象。
# main.py 中后续会这样注册：
# app.include_router(knowledge.router, prefix="/api/knowledge", tags=["Knowledge"])
#
# 因此：
# GET  /pending-files -> 最终路径 GET  /api/knowledge/pending-files
# POST /rebuild       -> 最终路径 POST /api/knowledge/rebuild
router = APIRouter()
logger = get_logger(__name__)

ALLOWED_UPLOAD_EXTENSIONS = {".txt", ".pdf", ".docx"}
ALLOWED_UPLOAD_CONTENT_TYPES = {
    ".txt": {
        "text/plain",
        "application/octet-stream",
    },
    ".pdf": {
        "application/pdf",
        "application/octet-stream",
    },
    ".docx": {
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/octet-stream",
    },
}


def get_safe_upload_filename(filename: str) -> str:
    safe_name = Path(filename).name.strip()
    if not safe_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="上传文件名不能为空",
        )
    return safe_name


def validate_upload_file_name(filename: str) -> str:
    safe_name = get_safe_upload_filename(filename)
    
    suffix = Path(safe_name).suffix.lower()
    if any(ch in safe_name for ch in ("\\", "/", "\0")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="上传文件名包含非法字符",
        )

    if len(safe_name) > 255:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="上传文件名过长",
        )

    if suffix not in ALLOWED_UPLOAD_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="仅支持 txt、pdf、docx 文件",
        )

    return safe_name

def validate_upload_content_type(
    filename: str,
    content_type: str | None,
) -> None:
    suffix = Path(filename).suffix.lower()
    allowed_content_types = ALLOWED_UPLOAD_CONTENT_TYPES.get(suffix, set())

    if not content_type:
        return

    if content_type not in allowed_content_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"文件类型不匹配：{content_type}",
        )

def build_upload_file_path(
    context: RequestContext,
    filename: str,
) -> Path:
    settings = get_settings()
    knowledge_base_id = context.knowledge_base_id or "default"
    upload_dir = Path(settings.knowledge_upload_dir) / context.tenant_id / knowledge_base_id
    upload_dir.mkdir(parents=True, exist_ok=True)

    suffix = Path(filename).suffix.lower()
    return upload_dir / f"{uuid4().hex}{suffix}"


def read_upload_file_bytes(file: UploadFile) -> bytes:
    settings = get_settings()
    content = file.file.read()
    max_size = settings.max_upload_file_size_mb * 1024 * 1024

    if not content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="上传文件内容不能为空",
        )

    if len(content) > max_size:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"上传文件不能超过 {settings.max_upload_file_size_mb} MB",
        )

    return content



# 创建 RAG 服务实例。
#
# 当前阶段：
# - 直接初始化，简单直观。
#
# 后续企业级优化：
# - 可以改成依赖注入。
# - 可以将知识库重建改成异步任务。
# - 可以增加 tenant_id / knowledge_base_id。
rag_service = RagService()
task_service = TaskService()   # 知识库重建改成异步任务。
document_service = DocumentService()
knowledge_base_service = KnowledgeBaseService()

def resolve_request_knowledge_base(
    context: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
) -> RequestContext:
    knowledge_base = knowledge_base_service.resolve_knowledge_base(
        db=db,
        context=context,
    )

    if not knowledge_base:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="知识库不存在或无权访问",
        )

    return context.model_copy(
        update={
            "knowledge_base_id": knowledge_base.id,
        }
    )


def run_document_ingest_task(
    task_id: str,
    context: RequestContext,
    document_version_id: str,
) -> None:
    """
    后台执行单个文档版本入库任务。
    """

    db = SessionLocal()

    try:
        task_service.mark_running(
            db=db,
            task_id=task_id,
            message="文档入库中",
        )

        def update_progress(
            progress: int,
            message: str,
            result: dict | None = None,
        ) -> None:
            task_service.mark_progress(
                db=db,
                task_id=task_id,
                progress=progress,
                message=message,
                result=result,
            )

        result = rag_service.ingest_document_version(
            db=db,
            context=context,
            document_version_id=document_version_id,
            progress_callback=update_progress,
        )

        task_service.mark_success(
            db=db,
            task_id=task_id,
            result=result,
            message="文档入库完成",
        )

    except Exception as exc:
        task_service.mark_failed(
            db=db,
            task_id=task_id,
            error=str(exc),
            message="文档入库失败",
        )

    finally:
        db.close()


def run_rebuild_knowledge_task(
    task_id: str,
    context: RequestContext,
) -> None:
    """
    后台执行知识库重建任务。

    注意：
    BackgroundTasks 运行时不能复用请求里的 db session，
    所以这里单独创建 SessionLocal。
    """

    db = SessionLocal()

    try:
        task_service.mark_running(
            db=db,
            task_id=task_id,
            message="知识库重建中",
        )

        result = rag_service.rebuild_knowledge_base(
            db=db,
            context=context,
        )

        task_service.mark_success(
            db=db,
            task_id=task_id,
            result=result,
            message="知识库重建完成",
        )

    except Exception as exc:
        task_service.mark_failed(
            db=db,
            task_id=task_id,
            error=str(exc),
            message="知识库重建失败",
        )

    finally:
        db.close()


@router.get("/pending-files")
def list_pending_files(
    context: RequestContext = Depends(resolve_request_knowledge_base),
    db: Session = Depends(get_db),
) -> dict:
    require_permission(context, "knowledge:read")
    try:
        return {
            "files": rag_service.list_pending_files(
                db=db,
                context=context,
            ),
        }
    except Exception as exc:
        logger.exception(
            "knowledge_pending_files_failed",
            extra=context.log_extra(),
        )
        raise HTTPException(
            status_code=500,
            detail="获取待入库文件失败，请稍后重试",
        ) from exc


@router.post(
    "/rebuild",
    response_model=KnowledgeTaskSubmitResponse,
)
def rebuild_knowledge_base(
    background_tasks: BackgroundTasks,
    context: RequestContext = Depends(resolve_request_knowledge_base),
    db: Session = Depends(get_db),
) -> KnowledgeTaskSubmitResponse:
    require_permission(context, "knowledge:write")
    try:
        active_task = task_service.get_active_knowledge_task(
            db=db,
            context=context,
            task_type="knowledge_rebuild",
        )

        if active_task:
            return KnowledgeTaskSubmitResponse(
                task_id=active_task.id,
                status=active_task.status,
                message="已有知识库重建任务正在执行",
            )

        task = task_service.create_knowledge_task(
            db=db,
            context=context,
            task_type="knowledge_rebuild",
            message="知识库重建任务已提交",
        )

        background_tasks.add_task(
            run_rebuild_knowledge_task,
            task_id=task.id,
            context=context,
        )

        return KnowledgeTaskSubmitResponse(
            task_id=task.id,
            status=task.status,
            message="知识库重建任务已提交",
        )

    except Exception as exc:
        logger.exception(
            "knowledge_rebuild_submit_failed",
            extra=context.log_extra(),
        )
        raise HTTPException(
            status_code=500,
            detail="提交知识库重建任务失败，请稍后重试",
        ) from exc
    

@router.post(
    "/search",
    response_model=RagAnswerResponse,
)
def search_knowledge_base(
    request: RagSearchRequest,
    context: RequestContext = Depends(resolve_request_knowledge_base),
) -> RagAnswerResponse:
    require_permission(context, "knowledge:read")
    return rag_service.search(
        query=request.query,
        context=context,
    )



@router.post(
    "/documents/upload",
    response_model=DocumentUploadResponse,
)
def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    context: RequestContext = Depends(resolve_request_knowledge_base),
    db: Session = Depends(get_db),
) -> DocumentUploadResponse:
    require_permission(context, "knowledge:write")
    filename = validate_upload_file_name(file.filename or "")
    validate_upload_content_type(filename, file.content_type)
    content = read_upload_file_bytes(file)
    file_hash = hashlib.md5(content).hexdigest()
    upload_path = build_upload_file_path(
        context=context,
        filename=filename,
    )
    
    upload_path.write_bytes(content)

    document, document_version = document_service.create_uploaded_document(
        db=db,
        context=context,
        file_name=filename,
        file_path=str(upload_path),
        file_hash=file_hash,
    )

    task = task_service.create_knowledge_task(
        db=db,
        context=context,
        task_type="document_ingest",
        message="文档上传成功，入库任务已创建",
    )

    background_tasks.add_task(
        run_document_ingest_task,
        task_id=task.id,
        context=context,
        document_version_id=document_version.id,
    )
    logger.info(
        "knowledge_document_uploaded",
        extra={
            **context.log_extra(),
            "file_name": filename,
            "file_size": len(content),
            "file_hash": file_hash,
            "document_id": document.id,
            "document_version_id": document_version.id,
            "task_id": task.id,
        },
    )

    return DocumentUploadResponse(
        document_id=document.id,
        document_version_id=document_version.id,
        task_id=task.id,
        status=task.status,
        message="文档上传成功，入库任务已创建",
    )

@router.get(
    "/documents",
    response_model=DocumentListResponse,
)
def list_documents(
    limit: int = 20,
    offset: int = 0,
    context: RequestContext = Depends(resolve_request_knowledge_base),
    db: Session = Depends(get_db),
) -> DocumentListResponse:
    require_permission(context, "knowledge:read")
    return document_service.list_documents(
        db=db,
        context=context,
        limit=limit,
        offset=offset,
    )


@router.delete(
    "/documents/{document_id}",
    response_model=SuccessResponse,
)
def delete_document(
    document_id: str,
    context: RequestContext = Depends(resolve_request_knowledge_base),
    db: Session = Depends(get_db),
) -> SuccessResponse:
    require_permission(context, "knowledge:delete")
    try:
        result = rag_service.soft_delete_document(
            db=db,
            context=context,
            document_id=document_id,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        logger.exception(
            "knowledge_document_delete_failed",
            extra=context.log_extra(),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="删除文档失败，请稍后重试",
        ) from exc

    return SuccessResponse(
        success=True,
        message=(
            f"文档已删除，失效版本 {result['deleted_versions']} 个，"
            f"删除向量 {result['deleted_vectors']} 条"
        ),
    )


@router.post(
    "/documents/{document_id}/versions/{document_version_id}/rollback",
    response_model=SuccessResponse,
)
def rollback_document_version(
    document_id: str,
    document_version_id: str,
    context: RequestContext = Depends(resolve_request_knowledge_base),
    db: Session = Depends(get_db),
) -> SuccessResponse:
    require_permission(context, "knowledge:write")
    try:
        result = rag_service.rollback_document_version(
            db=db,
            context=context,
            document_id=document_id,
            document_version_id=document_version_id,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        logger.exception(
            "knowledge_document_rollback_failed",
            extra=context.log_extra(),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="版本回滚失败，请稍后重试",
        ) from exc

    return SuccessResponse(
        success=True,
        message=(
            f"文档已回滚到版本 {result['document_version_id']}，"
            f"恢复向量 {result['restored_vectors']} 条"
        ),
    )


@router.get(
    "/documents/{document_id}",
    response_model=DocumentDetailResponse,
)
def get_document_detail(
    document_id: str,
    context: RequestContext = Depends(resolve_request_knowledge_base),
    db: Session = Depends(get_db),
) -> DocumentDetailResponse:
    require_permission(context, "knowledge:read")

    detail = document_service.get_document_detail(
        db=db,
        context=context,
        document_id=document_id,
    )

    if not detail:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="文档不存在或无权访问",
        )

    return detail

@router.get(
    "/documents/{document_id}/versions",
    response_model=DocumentVersionListResponse,
)
def list_document_versions(
    document_id: str,
    context: RequestContext = Depends(resolve_request_knowledge_base),
    db: Session = Depends(get_db),
) -> DocumentVersionListResponse:
    require_permission(context, "knowledge:read")
    versions = document_service.list_document_version_items(
        db=db,
        context=context,
        document_id=document_id,
    )

    if versions is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="文档不存在或无权访问",
        )

    return versions

@router.get(
    "/documents/{document_id}/chunks",
    response_model=KnowledgeChunkListResponse,
)
def list_document_chunks(
    document_id: str,
    document_version_id: str | None = None,
    limit: int = 50,
    offset: int = 0,
    context: RequestContext = Depends(resolve_request_knowledge_base),
    db: Session = Depends(get_db),
) -> KnowledgeChunkListResponse:
    require_permission(context, "knowledge:read")
    chunks = document_service.list_document_chunk_items(
        db=db,
        context=context,
        document_id=document_id,
        document_version_id=document_version_id,
        limit=limit,
        offset=offset,
    )

    if chunks is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="文档不存在或无权访问",
        )

    return chunks

@router.get(
    "/tasks",
    response_model=KnowledgeTaskListResponse,
)
def list_knowledge_tasks(
    limit: int = 20,
    offset: int = 0,
    context: RequestContext = Depends(resolve_request_knowledge_base),
    db: Session = Depends(get_db),
) -> KnowledgeTaskListResponse:
    require_permission(context, "knowledge:read")
    return task_service.list_knowledge_tasks(
        db=db,
        context=context,
        limit=limit,
        offset=offset,
    )

@router.get(
    "/tasks/{task_id}",
    response_model=KnowledgeTaskDetailResponse,
)
def get_knowledge_task(
    task_id: str,
    context: RequestContext = Depends(resolve_request_knowledge_base),
    db: Session = Depends(get_db),
) -> KnowledgeTaskDetailResponse:
    require_permission(context, "knowledge:read")
    task = task_service.get_knowledge_task(
        db=db,
        context=context,
        task_id=task_id,
    )

    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="任务不存在或无权访问",
        )

    return task

@router.post(
    "/bases",
    response_model=KnowledgeBaseCreateResponse,
)
def create_knowledge_base(
    request: KnowledgeBaseCreateRequest,
    context: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
) -> KnowledgeBaseCreateResponse:
    require_permission(context, "knowledge:write")
    return knowledge_base_service.create_knowledge_base(
        db=db,
        context=context,
        request=request,
    )

@router.get(
    "/bases",
    response_model=KnowledgeBaseListResponse,
)
def list_knowledge_bases(
    limit: int = 20,
    offset: int = 0,
    context: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
) -> KnowledgeBaseListResponse:
    require_permission(context, "knowledge:read")
    return knowledge_base_service.list_knowledge_bases(
        db=db,
        context=context,
        limit=limit,
        offset=offset,
    )








