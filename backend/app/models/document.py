"""Document upload and listing models."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel


class DocumentType(str, Enum):
    soil_report = "soil_report"
    field_photo = "field_photo"
    compliance = "compliance"


class DocumentResponse(BaseModel):
    """Row of public.documents (migrations 001 + 20260913000008).

    user_id, file_name and size_bytes were added later, so rows uploaded
    before that migration can have them null.
    """

    id: str
    farm_id: str
    user_id: str | None = None
    doc_type: DocumentType
    file_name: str | None = None
    storage_path: str
    size_bytes: int | None = None
    description: str | None = None
    uploaded_at: datetime | None = None
    created_at: datetime
