"""
Tests for app.routers.documents — upload, list, delete.

Auth and Supabase are replaced via FastAPI dependency_overrides. Supabase is a
FakeSupabase (tests/test_schema_drift.py) that records every write, so tests
can assert payloads use string ids and only columns that exist in the
migrations. Storage is a MagicMock.
"""

from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from postgrest.exceptions import APIError
from storage3.utils import StorageException

from app.auth.middleware import get_authenticated_client, get_current_user
from app.main import app
from app.routers.documents import _declared_size_too_large, _sanitize_filename
from tests.test_schema_drift import FakeSupabase, table_columns

_BASE = "/api/v1/documents"
_USER_ID = "0b6c1a52-7a0e-4d7e-9a51-3f7c2d1e0a11"
_FARM_ID = "5b0f3c1e-2a4d-4c1e-9b2a-6d7e8f901234"
_DOC_ID = "9d8c7b6a-5f4e-4d3c-8b2a-1f0e9d8c7b6a"
_STORAGE_PATH = f"{_USER_ID}/{_FARM_ID}/soil_report/abc_report.pdf"

_DOC_ROW = {
    "id": _DOC_ID,
    "farm_id": _FARM_ID,
    "user_id": _USER_ID,
    "doc_type": "soil_report",
    "file_name": "report.pdf",
    "storage_path": _STORAGE_PATH,
    "size_bytes": 3,
    "description": None,
    "uploaded_at": "2026-09-01T10:00:00+00:00",
    "created_at": "2026-09-01T10:00:00+00:00",
}


def _no_rows_error() -> APIError:
    return APIError({"message": "boom", "code": "XX000", "hint": None, "details": None})


@pytest.fixture
def make_client():
    def _make(supabase: FakeSupabase) -> TestClient:
        user = MagicMock()
        user.id = _USER_ID
        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_authenticated_client] = lambda: supabase
        return TestClient(app)

    try:
        yield _make
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_authenticated_client, None)


def _upload(client: TestClient, filename: str = "report.pdf", content: bytes = b"abc"):
    return client.post(
        f"{_BASE}/",
        data={"farm_id": _FARM_ID, "doc_type": "soil_report", "description": "Spring test"},
        files={"file": (filename, content, "application/pdf")},
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class TestSanitizeFilename:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("report.pdf", "report.pdf"),
            ("My Report!.pdf", "My_Report_.pdf"),
            ("../../etc/passwd", "passwd"),
            ("C:\\Users\\me\\soil test.pdf", "soil_test.pdf"),
            ("..hidden", "hidden"),
            ("..", ""),
            ("", ""),
        ],
    )
    def test_basename_and_safe_charset(self, raw, expected):
        assert _sanitize_filename(raw) == expected

    def test_long_names_are_truncated(self):
        assert len(_sanitize_filename("a" * 500 + ".pdf")) == 200


class TestDeclaredSize:
    def test_missing_header_is_not_too_large(self):
        assert _declared_size_too_large(None) is False

    def test_large_header_is_too_large(self):
        assert _declared_size_too_large(str(20 * 1024 * 1024)) is True

    @pytest.mark.parametrize("bad", ["abc", "12.5", "-1"])
    def test_malformed_header_raises_400(self, bad):
        with pytest.raises(HTTPException) as exc_info:
            _declared_size_too_large(bad)
        assert exc_info.value.status_code == 400


# ---------------------------------------------------------------------------
# POST /api/v1/documents/
# ---------------------------------------------------------------------------


class TestUploadDocument:
    def test_upload_inserts_real_columns_with_string_ids(self, make_client):
        supabase = FakeSupabase(rows={"farms": [{"id": _FARM_ID}]})
        client = make_client(supabase)

        response = _upload(client, filename="../secret/Soil Test #1.pdf")

        assert response.status_code == 201, response.text
        inserts = supabase.writes_for("documents", "insert")
        assert len(inserts) == 1
        payload = inserts[0]
        assert set(payload) <= table_columns("documents")
        assert payload["farm_id"] == _FARM_ID and isinstance(payload["farm_id"], str)
        assert payload["user_id"] == _USER_ID
        assert payload["size_bytes"] == 3
        assert "/" not in payload["file_name"]
        assert payload["file_name"].endswith("Test__1.pdf")

        body = response.json()
        assert body["file_name"] == payload["file_name"]
        assert body["size_bytes"] == 3
        assert "created_at" in body

    def test_storage_path_starts_with_user_id(self, make_client):
        """storage.objects policies only allow objects under <auth.uid()>/..."""
        supabase = FakeSupabase(rows={"farms": [{"id": _FARM_ID}]})
        client = make_client(supabase)

        _upload(client)

        upload_kwargs = supabase.storage.from_.return_value.upload.call_args.kwargs
        segments = upload_kwargs["path"].split("/")
        assert segments[0] == _USER_ID
        assert segments[1] == _FARM_ID
        assert segments[2] == "soil_report"
        assert len(segments) == 4
        supabase.storage.from_.assert_called_with("farm-documents")

    def test_farm_not_found_returns_404_without_storage_write(self, make_client):
        supabase = FakeSupabase(rows={"farms": []})
        client = make_client(supabase)

        response = _upload(client)

        assert response.status_code == 404
        supabase.storage.from_.return_value.upload.assert_not_called()
        assert supabase.writes == []

    def test_storage_failure_returns_500_without_insert(self, make_client):
        supabase = FakeSupabase(rows={"farms": [{"id": _FARM_ID}]})
        supabase.storage.from_.return_value.upload.side_effect = StorageException("down")
        client = make_client(supabase)

        response = _upload(client)

        assert response.status_code == 500
        assert supabase.writes_for("documents", "insert") == []

    def test_insert_failure_returns_500_and_removes_object(self, make_client):
        supabase = FakeSupabase(
            rows={"farms": [{"id": _FARM_ID}]},
            errors={("documents", "insert"): _no_rows_error()},
        )
        client = make_client(supabase)

        response = _upload(client)

        assert response.status_code == 500
        bucket = supabase.storage.from_.return_value
        uploaded_path = bucket.upload.call_args.kwargs["path"]
        bucket.remove.assert_called_once_with([uploaded_path])

    def test_oversized_file_returns_413(self, make_client, monkeypatch):
        monkeypatch.setattr("app.routers.documents._MAX_FILE_SIZE_BYTES", 2)
        supabase = FakeSupabase(rows={"farms": [{"id": _FARM_ID}]})
        client = make_client(supabase)

        response = _upload(client, content=b"abcdef")

        assert response.status_code == 413
        supabase.storage.from_.return_value.upload.assert_not_called()


# ---------------------------------------------------------------------------
# GET /api/v1/documents/
# ---------------------------------------------------------------------------


class TestListDocuments:
    def test_list_orders_by_created_at_with_string_farm_id(self, make_client):
        supabase = FakeSupabase(rows={"farms": [{"id": _FARM_ID}], "documents": [_DOC_ROW]})
        client = make_client(supabase)

        response = client.get(f"{_BASE}/", params={"farm_id": _FARM_ID, "doc_type": "soil_report"})

        assert response.status_code == 200
        assert response.json()[0]["id"] == _DOC_ID
        query = supabase.last_query("documents")
        assert ("eq", ("farm_id", _FARM_ID)) in query.filters
        assert ("eq", ("doc_type", "soil_report")) in query.filters
        order_calls = [args for name, args in query.filters if name == "order"]
        assert order_calls == [("created_at",)]
        assert "created_at" in table_columns("documents")

    def test_legacy_row_without_new_columns_still_serializes(self, make_client):
        legacy = {
            "id": _DOC_ID,
            "farm_id": _FARM_ID,
            "doc_type": "compliance",
            "storage_path": "old/path.pdf",
            "uploaded_at": "2026-04-01T00:00:00+00:00",
            "created_at": "2026-04-01T00:00:00+00:00",
            "user_id": None,
            "file_name": None,
            "size_bytes": None,
            "description": None,
        }
        supabase = FakeSupabase(rows={"farms": [{"id": _FARM_ID}], "documents": [legacy]})
        client = make_client(supabase)

        response = client.get(f"{_BASE}/", params={"farm_id": _FARM_ID})

        assert response.status_code == 200
        assert response.json()[0]["file_name"] is None

    def test_list_unknown_farm_returns_404(self, make_client):
        client = make_client(FakeSupabase(rows={"farms": []}))
        response = client.get(f"{_BASE}/", params={"farm_id": _FARM_ID})
        assert response.status_code == 404

    def test_list_db_error_returns_500(self, make_client):
        supabase = FakeSupabase(
            rows={"farms": [{"id": _FARM_ID}]},
            errors={("documents", "select"): _no_rows_error()},
        )
        client = make_client(supabase)
        response = client.get(f"{_BASE}/", params={"farm_id": _FARM_ID})
        assert response.status_code == 500


# ---------------------------------------------------------------------------
# DELETE /api/v1/documents/{doc_id}
# ---------------------------------------------------------------------------


class TestDeleteDocument:
    def test_delete_removes_row_then_object(self, make_client):
        supabase = FakeSupabase(rows={"documents": [_DOC_ROW]})
        client = make_client(supabase)

        response = client.delete(f"{_BASE}/{_DOC_ID}")

        assert response.status_code == 204
        delete_query = supabase.last_query("documents")
        assert delete_query.op == "delete"
        assert ("eq", ("id", _DOC_ID)) in delete_query.filters
        supabase.storage.from_.return_value.remove.assert_called_once_with([_STORAGE_PATH])
        # RLS already scopes the lookup; no redundant farm re-check.
        assert "farms" not in supabase.tables_queried()

    def test_delete_missing_document_returns_404(self, make_client):
        supabase = FakeSupabase(rows={"documents": []})
        client = make_client(supabase)

        response = client.delete(f"{_BASE}/{_DOC_ID}")

        assert response.status_code == 404
        assert all(q.op != "delete" for q in supabase.queries)
        supabase.storage.from_.return_value.remove.assert_not_called()

    def test_delete_lookup_error_returns_500(self, make_client):
        supabase = FakeSupabase(errors={("documents", "select"): _no_rows_error()})
        client = make_client(supabase)
        response = client.delete(f"{_BASE}/{_DOC_ID}")
        assert response.status_code == 500

    def test_delete_non_uuid_returns_422(self, make_client):
        client = make_client(FakeSupabase())
        response = client.delete(f"{_BASE}/not-a-uuid")
        assert response.status_code == 422

    def test_storage_removal_failure_is_non_fatal(self, make_client):
        supabase = FakeSupabase(rows={"documents": [_DOC_ROW]})
        supabase.storage.from_.return_value.remove.side_effect = StorageException("gone")
        client = make_client(supabase)

        response = client.delete(f"{_BASE}/{_DOC_ID}")

        assert response.status_code == 204
