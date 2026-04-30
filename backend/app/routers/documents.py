"""
Document Upload & Management router for RegenAI.

Exposes endpoints for uploading, listing, and deleting farm documents.
Supported document types (soil_report, field_photo, compliance) are the
exact set that the EQIP eligibility engine queries to determine whether a
farm has sufficient documentation to move from 'pending_review' to 'eligible'.

All endpoints require a valid Supabase JWT (Bearer token). Row Level Security
policies are enforced through the authenticated Supabase client, so users can
only access documents belonging to farms they own.

Upload constraints:
    - Maximum file size: 10 MB (10_485_760 bytes)
    - Allowed doc_type values: soil_report, field_photo, compliance
    - Files are stored in the 'farm-documents' Supabase Storage bucket under
      the path  <user_id>/<farm_id>/<doc_type>/<uuid>_<original_filename>
"""

import logging
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile

from app.auth.middleware import get_authenticated_client, get_current_user
from app.models.schemas import DocumentCreate, DocumentResponse, DocumentType

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/documents", tags=["Documents"])

# Supabase Storage bucket name — must be created in the Supabase dashboard.
_STORAGE_BUCKET = "farm-documents"

# 10 MB hard limit enforced before the bytes reach Supabase Storage.
_MAX_FILE_SIZE = 10 * 1024 * 1024  # 10_485_760 bytes


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_storage_path(user_id: str, farm_id: str, doc_type: str, filename: str) -> str:
    """Return a deterministic, collision-safe storage path for a document."""
    safe_name = filename.replace(" ", "_")
    unique_prefix = str(uuid.uuid4())
    return f"{user_id}/{farm_id}/{doc_type}/{unique_prefix}_{safe_name}"


async def _assert_farm_ownership(farm_id: str, supabase) -> None:
    """Raise HTTP 404 if the farm does not exist or is not accessible via RLS."""
    result = supabase.table("farms").select("id").eq("id", farm_id).single().execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Farm not found")


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/", response_model=DocumentResponse, status_code=201)
async def upload_document(
    farm_id: Annotated[str, Form(description="UUID of the farm this document belongs to")],
    doc_type: Annotated[DocumentType, Form(description="Document category")],
    file: Annotated[UploadFile, File(description="File to upload (max 10 MB)")],
    description: Annotated[str | None, Form(max_length=500)] = None,
    user=Depends(get_current_user),
    supabase=Depends(get_authenticated_client),
):
    """Upload a document for a farm and record its metadata in the documents table.

    The file is streamed into Supabase Storage under a user/farm-scoped path.
    A metadata row is then inserted into the ``documents`` table. The EQIP
    eligibility engine will detect qualifying doc_type values (soil_report,
    field_photo, compliance) on its next evaluation run.

    Args:
        farm_id: UUID of the farm (must be owned by the authenticated user).
        doc_type: One of soil_report | field_photo | compliance.
        file: Multipart file, must be <= 10 MB.
        description: Optional human-readable description of the document.

    Returns:
        DocumentResponse with storage path and metadata.

    Raises:
        HTTPException 400: File exceeds 10 MB limit or no filename provided.
        HTTPException 404: Farm not found (or not accessible to the user).
        HTTPException 500: Storage upload or database insert failure.
    """
    # Validate farm ownership (RLS provides isolation, this gives a clean 404).
    await _assert_farm_ownership(farm_id, supabase)

    # Enforce filename requirement.
    filename = file.filename or ""
    if not filename:
        raise HTTPException(status_code=400, detail="Uploaded file must have a filename.")

    # Read file into memory and enforce size limit.
    contents = await file.read()
    size_bytes = len(contents)
    if size_bytes > _MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"File size {size_bytes:,} bytes exceeds the 10 MB limit.",
        )

    # Build storage path and upload to Supabase Storage.
    storage_path = _build_storage_path(str(user.id), farm_id, doc_type.value, filename)

    try:
        supabase.storage.from_(_STORAGE_BUCKET).upload(
            path=storage_path,
            file=contents,
            file_options={"content-type": file.content_type or "application/octet-stream"},
        )
    except Exception as exc:
        logger.exception(
            "documents.upload: storage upload failed farm=%s path=%s error=%s",
            farm_id,
            storage_path,
            exc,
        )
        raise HTTPException(status_code=500, detail="Failed to upload file to storage.")

    # Insert metadata row into the documents table.
    row = {
        "farm_id": farm_id,
        "user_id": str(user.id),
        "doc_type": doc_type.value,
        "file_name": filename,
        "storage_path": storage_path,
        "size_bytes": size_bytes,
        "description": description,
    }

    try:
        result = supabase.table("documents").insert(row).execute()
        if not result.data:
            raise RuntimeError("Insert returned no data")
        inserted = result.data[0]
    except Exception as exc:
        logger.exception(
            "documents.upload: db insert failed farm=%s path=%s error=%s",
            farm_id,
            storage_path,
            exc,
        )
        # Best-effort cleanup of the orphaned storage object.
        try:
            supabase.storage.from_(_STORAGE_BUCKET).remove([storage_path])
        except Exception:
            logger.warning(
                "documents.upload: orphaned storage object at path=%s", storage_path
            )
        raise HTTPException(status_code=500, detail="Failed to record document metadata.")

    logger.info(
        "documents.upload: success farm=%s doc_type=%s size_bytes=%d path=%s",
        farm_id,
        doc_type.value,
        size_bytes,
        storage_path,
    )
    return inserted


@router.get("/", response_model=list[DocumentResponse])
async def list_documents(
    farm_id: str = Query(..., description="UUID of the farm to list documents for"),
    doc_type: DocumentType | None = Query(None, description="Filter by document type"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    user=Depends(get_current_user),
    supabase=Depends(get_authenticated_client),
):
    """List documents for a farm, optionally filtered by doc_type.

    RLS ensures only documents belonging to farms the authenticated user owns
    are returned. Pagination is supported via limit/offset.

    Args:
        farm_id: UUID of the farm (required).
        doc_type: Optional filter — one of soil_report | field_photo | compliance.
        limit: Page size (1–200, default 50).
        offset: Row offset for pagination (default 0).

    Returns:
        List of DocumentResponse ordered by created_at descending.

    Raises:
        HTTPException 404: Farm not found (or not accessible to the user).
        HTTPException 500: Database query failure.
    """
    await _assert_farm_ownership(farm_id, supabase)

    try:
        query = (
            supabase.table("documents")
            .select("*")
            .eq("farm_id", farm_id)
            .order("created_at", desc=True)
            .range(offset, offset + limit - 1)
        )
        if doc_type is not None:
            query = query.eq("doc_type", doc_type.value)

        result = query.execute()
    except Exception as exc:
        logger.exception(
            "documents.list: query failed farm=%s error=%s", farm_id, exc
        )
        raise HTTPException(status_code=500, detail="Failed to retrieve documents.")

    return result.data or []


@router.delete("/{doc_id}", status_code=204)
async def delete_document(
    doc_id: str,
    user=Depends(get_current_user),
    supabase=Depends(get_authenticated_client),
):
    """Delete a document record and remove the file from Supabase Storage.

    The requesting user must own the farm the document belongs to. RLS prevents
    cross-user access; the explicit farm ownership check provides a clean 404
    rather than a cryptic empty-result response.

    Args:
        doc_id: UUID of the document to delete.

    Returns:
        204 No Content on success.

    Raises:
        HTTPException 404: Document not found (or not accessible to the user).
        HTTPException 500: Database deletion failure.
    """
    # Fetch the document — RLS will filter out records the user doesn't own.
    try:
        result = (
            supabase.table("documents")
            .select("id, farm_id, storage_path, user_id")
            .eq("id", doc_id)
            .single()
            .execute()
        )
    except Exception as exc:
        logger.exception(
            "documents.delete: fetch failed doc_id=%s error=%s", doc_id, exc
        )
        raise HTTPException(status_code=404, detail="Document not found")

    if not result.data:
        raise HTTPException(status_code=404, detail="Document not found")

    doc = result.data
    storage_path: str = doc["storage_path"]

    # Verify the user owns the farm (belt-and-suspenders over RLS).
    farm_check = (
        supabase.table("farms")
        .select("id")
        .eq("id", doc["farm_id"])
        .single()
        .execute()
    )
    if not farm_check.data:
        raise HTTPException(status_code=404, detail="Document not found")

    # Delete the metadata row first — if storage removal fails the DB stays clean.
    try:
        supabase.table("documents").delete().eq("id", doc_id).execute()
    except Exception as exc:
        logger.exception(
            "documents.delete: db delete failed doc_id=%s error=%s", doc_id, exc
        )
        raise HTTPException(status_code=500, detail="Failed to delete document record.")

    # Remove file from storage (non-fatal if the object is already gone).
    try:
        supabase.storage.from_(_STORAGE_BUCKET).remove([storage_path])
    except Exception as exc:
        logger.warning(
            "documents.delete: storage removal failed path=%s error=%s",
            storage_path,
            exc,
        )

    logger.info(
        "documents.delete: success doc_id=%s farm=%s path=%s",
        doc_id,
        doc["farm_id"],
        storage_path,
    )
