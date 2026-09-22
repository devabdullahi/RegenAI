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
    - Maximum file size: see _MAX_FILE_SIZE_MB below
    - Allowed doc_type values: soil_report, field_photo, compliance
    - Files are stored in the private 'farm-documents' Supabase Storage bucket
      under <user_id>/<farm_id>/<doc_type>/<uuid>_<safe_filename>. The first
      path segment must be the user's id: the storage.objects policies in
      migration 20260913000008 only allow access under auth.uid().
"""

import logging
import re
import uuid
from typing import Annotated
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from postgrest.exceptions import APIError
from storage3.utils import StorageException

from app.auth.access import assert_farm_access
from app.auth.middleware import get_authenticated_client, get_current_user
from app.models.schemas import DocumentResponse, DocumentType
from app.rate_limit import limiter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/documents", tags=["Documents"])

# Private bucket created by migration 20260913000008.
_STORAGE_BUCKET = "farm-documents"

# Hard limit enforced before the bytes reach Supabase Storage.
_MAX_FILE_SIZE_MB = 10
_MAX_FILE_SIZE_BYTES = _MAX_FILE_SIZE_MB * 1024 * 1024

_MAX_FILENAME_LENGTH = 200
_UNSAFE_FILENAME_CHARS = re.compile(r"[^A-Za-z0-9._-]")

# Errors the storage client raises for failed or unreachable requests.
_STORAGE_ERRORS = (StorageException, httpx.HTTPError)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _sanitize_filename(filename: str) -> str:
    """Reduce a client-supplied filename to a safe basename.

    Strips any directory part (either slash style) so the name cannot move the
    object outside the user's folder, then replaces characters outside
    [A-Za-z0-9._-]. Leading dots are removed so the name is never hidden or
    relative. Returns "" when nothing usable remains.
    """
    basename = filename.replace("\\", "/").rsplit("/", 1)[-1]
    safe_name = _UNSAFE_FILENAME_CHARS.sub("_", basename).lstrip(".")
    return safe_name[-_MAX_FILENAME_LENGTH:]


def _build_storage_path(user_id: str, farm_id: str, doc_type: str, safe_name: str) -> str:
    """Return a collision-safe storage path whose first segment is the user id."""
    return f"{user_id}/{farm_id}/{doc_type}/{uuid.uuid4()}_{safe_name}"


def _declared_size_too_large(content_length: str | None) -> bool:
    """Best-effort early size check from the Content-Length header.

    Raises:
        HTTPException 400: the header is present but not a non-negative integer.
    """
    if content_length is None:
        return False
    try:
        declared_bytes = int(content_length)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid Content-Length header.")
    if declared_bytes < 0:
        raise HTTPException(status_code=400, detail="Invalid Content-Length header.")
    return declared_bytes > _MAX_FILE_SIZE_BYTES


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/", response_model=DocumentResponse, status_code=201)
@limiter.limit("20/hour")
async def upload_document(
    request: Request,
    farm_id: Annotated[UUID, Form(description="UUID of the farm this document belongs to")],
    doc_type: Annotated[DocumentType, Form(description="Document category")],
    file: Annotated[UploadFile, File(description=f"File to upload (max {_MAX_FILE_SIZE_MB} MB)")],
    description: Annotated[str | None, Form(max_length=500)] = None,
    user=Depends(get_current_user),
    supabase=Depends(get_authenticated_client),
):
    """Upload a document for a farm and record its metadata in the documents table.

    The file is stored in Supabase Storage under a user/farm-scoped path, then
    a metadata row is inserted into ``documents``. If the insert fails the
    stored object is removed again (best effort).

    Raises:
        HTTPException 400: Missing/unusable filename or malformed Content-Length.
        HTTPException 404: Farm not found (or not accessible to the user).
        HTTPException 413: File exceeds the size limit.
        HTTPException 500: Storage upload or database insert failure.
    """
    farm_id_str = str(farm_id)
    user_id_str = str(user.id)
    assert_farm_access(farm_id_str, supabase)

    safe_name = _sanitize_filename(file.filename or "")
    if not safe_name:
        raise HTTPException(status_code=400, detail="Uploaded file must have a filename.")

    # Content-Length can be spoofed, so this is only an early rejection; the
    # size check after file.read() below is the authoritative one.
    if _declared_size_too_large(request.headers.get("content-length")):
        raise HTTPException(
            status_code=413,
            detail=f"File too large: request body exceeds the {_MAX_FILE_SIZE_MB} MB limit.",
        )

    contents = await file.read()
    size_bytes = len(contents)
    if size_bytes > _MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File size {size_bytes:,} bytes exceeds the {_MAX_FILE_SIZE_MB} MB limit.",
        )

    storage_path = _build_storage_path(user_id_str, farm_id_str, doc_type.value, safe_name)
    bucket = supabase.storage.from_(_STORAGE_BUCKET)

    try:
        bucket.upload(
            path=storage_path,
            file=contents,
            file_options={"content-type": file.content_type or "application/octet-stream"},
        )
    except _STORAGE_ERRORS as exc:
        logger.error(
            "documents.upload: storage upload failed farm=%s path=%s error=%s",
            farm_id_str,
            storage_path,
            exc,
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail="Failed to upload file to storage.")

    row = {
        "farm_id": farm_id_str,
        "user_id": user_id_str,
        "doc_type": doc_type.value,
        "file_name": safe_name,
        "storage_path": storage_path,
        "size_bytes": size_bytes,
        "description": description,
    }

    try:
        result = supabase.table("documents").insert(row).execute()
    except APIError as exc:
        logger.error(
            "documents.upload: db insert failed farm=%s path=%s error=%s",
            farm_id_str,
            storage_path,
            exc,
            exc_info=True,
        )
        result = None

    if not result or not result.data:
        try:
            bucket.remove([storage_path])
        except _STORAGE_ERRORS as exc:
            logger.warning(
                "documents.upload: orphaned storage object path=%s error=%s",
                storage_path,
                exc,
            )
        raise HTTPException(status_code=500, detail="Failed to record document metadata.")

    logger.info(
        "documents.upload: success farm=%s doc_type=%s size_bytes=%d path=%s",
        farm_id_str,
        doc_type.value,
        size_bytes,
        storage_path,
    )
    return result.data[0]


@router.get("/", response_model=list[DocumentResponse])
async def list_documents(
    farm_id: UUID = Query(..., description="UUID of the farm to list documents for"),
    doc_type: DocumentType | None = Query(None, description="Filter by document type"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    user=Depends(get_current_user),
    supabase=Depends(get_authenticated_client),
):
    """List documents for a farm (newest first), optionally filtered by doc_type.

    Raises:
        HTTPException 404: Farm not found (or not accessible to the user).
        HTTPException 500: Database query failure.
    """
    farm_id_str = str(farm_id)
    assert_farm_access(farm_id_str, supabase)

    query = supabase.table("documents").select("*").eq("farm_id", farm_id_str)
    if doc_type is not None:
        query = query.eq("doc_type", doc_type.value)

    try:
        result = query.order("created_at", desc=True).range(offset, offset + limit - 1).execute()
    except APIError as exc:
        logger.error(
            "documents.list: query failed farm=%s error=%s", farm_id_str, exc, exc_info=True
        )
        raise HTTPException(status_code=500, detail="Failed to retrieve documents.")

    return result.data or []


@router.delete("/{doc_id}", status_code=204)
async def delete_document(
    doc_id: UUID,
    user=Depends(get_current_user),
    supabase=Depends(get_authenticated_client),
):
    """Delete a document record and remove the file from Supabase Storage.

    RLS scopes the lookup to documents on the user's own farms, so a missing
    row means "not found or not yours" and returns 404.

    Raises:
        HTTPException 404: Document not found (or not accessible to the user).
        HTTPException 500: Database lookup or deletion failure.
    """
    doc_id_str = str(doc_id)

    try:
        result = (
            supabase.table("documents")
            .select("id, farm_id, storage_path")
            .eq("id", doc_id_str)
            .limit(1)
            .execute()
        )
    except APIError as exc:
        logger.error(
            "documents.delete: fetch failed doc_id=%s error=%s", doc_id_str, exc, exc_info=True
        )
        raise HTTPException(status_code=500, detail="Failed to look up document.")

    if not result.data:
        raise HTTPException(status_code=404, detail="Document not found")

    doc = result.data[0]
    storage_path: str = doc["storage_path"]

    # Delete the metadata row first — if storage removal fails the DB stays clean.
    try:
        supabase.table("documents").delete().eq("id", doc_id_str).execute()
    except APIError as exc:
        logger.error(
            "documents.delete: db delete failed doc_id=%s error=%s",
            doc_id_str,
            exc,
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail="Failed to delete document record.")

    # Non-fatal: the row is gone; an orphaned object is logged for cleanup.
    try:
        supabase.storage.from_(_STORAGE_BUCKET).remove([storage_path])
    except _STORAGE_ERRORS as exc:
        logger.warning(
            "documents.delete: storage removal failed doc_id=%s path=%s error=%s",
            doc_id_str,
            storage_path,
            exc,
        )

    logger.info(
        "documents.delete: success doc_id=%s farm=%s path=%s",
        doc_id_str,
        doc["farm_id"],
        storage_path,
    )
