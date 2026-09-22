"""
Tests for app.routers.health — GET /health (unversioned, used by load balancers).

The health handler calls get_supabase_client() directly rather than through
Depends(), so the module-level name is patched here.
"""

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.main import app


def test_health_ok_returns_200():
    """A reachable Supabase gives 200 and checks.supabase == 'ok'."""
    with patch("app.routers.health.get_supabase_client", return_value=MagicMock()):
        response = TestClient(app).get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "healthy",
        "service": "regenai-api",
        "checks": {"supabase": "ok"},
    }


def test_health_supabase_failure_returns_503_and_logs_error(caplog):
    """A connectivity failure degrades to 503 and the log carries the error message."""
    failing_client = MagicMock()
    failing_client.table.return_value.select.return_value.limit.return_value.execute.side_effect = (
        ConnectionError("connection refused")
    )

    with patch("app.routers.health.get_supabase_client", return_value=failing_client):
        with caplog.at_level("WARNING", logger="app.routers.health"):
            response = TestClient(app).get("/health")

    assert response.status_code == 503
    assert response.json()["checks"] == {"supabase": "error"}
    assert "connection refused" in caplog.text
