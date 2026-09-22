"""
Tests for app.services.recommendations and app.routers.recommendations.

The LLM client (DeepSeek via the OpenAI SDK) is always mocked; no test performs
a network call.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx2
import openai
import pytest
from postgrest.exceptions import APIError

from app.config import settings
from app.services.recommendations import (
    RecommendationOutputError,
    _call_llm,
    _parse_llm_json,
    _store_recommendations,
    _validate_recommendations,
    generate_recommendations,
)
from app.services.validators import (
    LLMPriority,
    LLMRecommendation,
    validate_field_ids,
    validate_practice_codes,
)

# LLMRecommendation.field_id is a UUID, so the conftest placeholder ids do not apply here.
FARM_ID = "0b6f7c1e-2d3a-4b5c-8d9e-0f1a2b3c4d5e"
FIELD_ID_A = "1a2b3c4d-5e6f-4a7b-8c9d-0e1f2a3b4c5d"
FIELD_ID_B = "2b3c4d5e-6f7a-4b8c-9d0e-1f2a3b4c5d6e"
UNKNOWN_FIELD_ID = "9f8e7d6c-5b4a-4938-8271-605f4e3d2c1b"

# openai 3.x is built on httpx2 (not httpx), so SDK errors carry httpx2 objects.
_LLM_REQUEST = httpx2.Request("POST", "https://api.deepseek.com/chat/completions")


def _status_error(cls, status_code: int):
    return cls(
        message=f"status {status_code}",
        response=httpx2.Response(status_code, request=_LLM_REQUEST),
        body={},
    )


def _connection_error():
    return openai.APIConnectionError(request=_LLM_REQUEST)


def _timeout_error():
    return openai.APITimeoutError(request=_LLM_REQUEST)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_rec(
    field_id: str = FIELD_ID_A,
    practice_code: str = "340",
    title: str = "Plant Cover Crops",
    rationale: str = "Cover crops improve soil health significantly.",
    priority: str = "high",
) -> LLMRecommendation:
    return LLMRecommendation(
        field_id=field_id,
        practice_code=practice_code,
        title=title,
        rationale=rationale,
        priority=LLMPriority(priority),
    )


def _raw_rec(field_id: str = FIELD_ID_A, practice_code: str = "340") -> dict:
    return {
        "field_id": field_id,
        "practice_code": practice_code,
        "title": "Plant Cover Crops",
        "rationale": "Cover crops significantly improve soil health and water retention.",
        "priority": "high",
    }


def _make_llm_response(content: str | None, finish_reason: str = "stop") -> MagicMock:
    """Build a fake OpenAI-style chat completion with a single choice."""
    choice = MagicMock()
    choice.message.content = content
    choice.finish_reason = finish_reason
    response = MagicMock()
    response.choices = [choice]
    return response


def _mock_client(**create_kwargs) -> MagicMock:
    client = MagicMock()
    client.chat.completions.create = AsyncMock(**create_kwargs)
    return client


_PATCH_LLM_CLIENT = "app.services.recommendations._llm_client"


# ---------------------------------------------------------------------------
# _call_llm
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestCallLLM:
    async def test_valid_response_returns_text_and_uses_settings(self):
        """The response text is returned and model params come from settings."""
        client = _mock_client(return_value=_make_llm_response('[{"field_id": "abc"}]'))

        with patch(_PATCH_LLM_CLIENT, client):
            result = await _call_llm("system prompt", "user message")

        assert result == '[{"field_id": "abc"}]'
        kwargs = client.chat.completions.create.await_args.kwargs
        assert kwargs["model"] == settings.deepseek_model
        assert kwargs["max_tokens"] == settings.llm_max_tokens
        assert kwargs["temperature"] == settings.llm_temperature
        assert kwargs["messages"] == [
            {"role": "system", "content": "system prompt"},
            {"role": "user", "content": "user message"},
        ]
        assert kwargs["extra_body"] == {"thinking": {"type": "disabled"}}

    async def test_surrounding_whitespace_stripped(self):
        client = _mock_client(return_value=_make_llm_response("  \n[]\n "))

        with patch(_PATCH_LLM_CLIENT, client):
            assert await _call_llm("system", "user") == "[]"

    async def test_empty_choices_returns_none(self):
        response = MagicMock()
        response.choices = []
        client = _mock_client(return_value=response)

        with patch(_PATCH_LLM_CLIENT, client):
            assert await _call_llm("system", "user") is None

    @pytest.mark.parametrize("content", [None, "", "   \n "], ids=["none", "empty", "blank"])
    async def test_no_content_returns_none(self, content):
        client = _mock_client(return_value=_make_llm_response(content))

        with patch(_PATCH_LLM_CLIENT, client):
            assert await _call_llm("system", "user") is None

    async def test_truncated_length_reply_is_logged_and_not_rescued(self, caplog):
        """A 'length' reply is returned as-is so strict parsing rejects it and the loop retries."""
        truncated = '[{"field_id": "abc", "practice_co'
        client = _mock_client(return_value=_make_llm_response(truncated, finish_reason="length"))

        with patch(_PATCH_LLM_CLIENT, client):
            result = await _call_llm("system", "user")

        assert result == truncated
        assert _parse_llm_json(result) is None
        assert "finish_reason=length" in caplog.text

    @pytest.mark.parametrize(
        "error",
        [
            _connection_error(),
            _timeout_error(),
            _status_error(openai.RateLimitError, 429),
            _status_error(openai.APIStatusError, 402),
            _status_error(openai.APIStatusError, 500),
        ],
        ids=["connection", "timeout", "rate_limit", "insufficient_balance", "status"],
    )
    async def test_llm_errors_propagate(self, error):
        """API errors must reach the router instead of becoming a silent None."""
        client = _mock_client(side_effect=error)

        with patch(_PATCH_LLM_CLIENT, client):
            with pytest.raises(type(error)):
                await _call_llm("system", "user")

    async def test_unexpected_exception_propagates(self):
        client = _mock_client(side_effect=RuntimeError("something exploded"))

        with patch(_PATCH_LLM_CLIENT, client):
            with pytest.raises(RuntimeError):
                await _call_llm("system", "user")


# ---------------------------------------------------------------------------
# _parse_llm_json (strict)
# ---------------------------------------------------------------------------

class TestParseLLMJson:
    def test_bare_array_accepted(self):
        result = _parse_llm_json('[{"field_id": "abc", "practice_code": "340"}]')
        assert result == [{"field_id": "abc", "practice_code": "340"}]

    def test_surrounding_whitespace_accepted(self):
        assert _parse_llm_json('  \n[{"practice_code": "329"}]\n ') == [{"practice_code": "329"}]

    def test_json_fenced_array_rejected(self):
        """The prompt forbids code fences, so a fenced array is not rescued."""
        raw = '```json\n[{"field_id": "abc"}]\n```'
        assert _parse_llm_json(raw) is None

    def test_empty_array_returns_empty_list(self):
        assert _parse_llm_json("[]") == []

    def test_multiple_items_parsed(self):
        raw = '[{"field_id":"a","practice_code":"340"},{"field_id":"b","practice_code":"329"}]'
        assert [item["practice_code"] for item in _parse_llm_json(raw)] == ["340", "329"]

    @pytest.mark.parametrize(
        "raw",
        [
            'Here are the recommendations:\n[{"practice_code": "329"}]',
            '[{"practice_code": "329"}]\nLet me know if you need more.',
            'Sure!\n```json\n[{"practice_code": "329"}]\n```',
            '```json\n[{"practice_code": "329"}]\n```\nHope this helps.',
            '```\n[{"practice_code": "329"}]\n```',
            '```json\n[{"a": 1}]\n```\n```json\n[{"b": 2}]\n```',
            '{"recommendations": [{"practice_code": "329"}]}',
            '```json\n{"recommendations": []}\n```',
            "[{field_id: no quotes here}]",
            "I am unable to generate recommendations at this time.",
            "   \n  ",
        ],
        ids=[
            "prose_before",
            "prose_after",
            "prose_before_fence",
            "prose_after_fence",
            "plain_fence",
            "two_fenced_blocks",
            "wrapped_object",
            "fenced_object",
            "invalid_json",
            "no_json",
            "whitespace",
        ],
    )
    def test_other_shapes_rejected(self, raw):
        assert _parse_llm_json(raw) is None


# ---------------------------------------------------------------------------
# _validate_recommendations
# ---------------------------------------------------------------------------

class TestValidateRecommendations:
    def test_valid_items_all_pass(self):
        result = _validate_recommendations(
            [_raw_rec(FIELD_ID_A, "340"), _raw_rec(FIELD_ID_B, "329")]
        )
        assert [(str(r.field_id), r.practice_code) for r in result] == [
            (FIELD_ID_A, "340"),
            (FIELD_ID_B, "329"),
        ]

    def test_invalid_item_skipped_valid_returned(self):
        missing_field_id = {k: v for k, v in _raw_rec().items() if k != "field_id"}
        result = _validate_recommendations([_raw_rec(practice_code="340"), missing_field_id])
        assert len(result) == 1
        assert result[0].practice_code == "340"

    def test_non_dict_items_and_extra_keys_skipped(self):
        result = _validate_recommendations(
            ["not an object", 42, {**_raw_rec(), "confidence": 0.9}]
        )
        assert result == []

    def test_non_uuid_field_id_skipped(self):
        assert _validate_recommendations([_raw_rec(field_id="field-uuid-aaaa")]) == []

    def test_empty_list_returns_empty(self):
        assert _validate_recommendations([]) == []

    def test_practice_code_whitespace_stripped(self):
        result = _validate_recommendations([_raw_rec(practice_code="  340  ")])
        assert result[0].practice_code == "340"

    def test_default_priority_medium_when_not_provided(self):
        raw = {k: v for k, v in _raw_rec().items() if k != "priority"}
        result = _validate_recommendations([raw])
        assert result[0].priority == LLMPriority.medium


# ---------------------------------------------------------------------------
# _store_recommendations
# ---------------------------------------------------------------------------

def _capturing_supabase(returned_rows=None):
    """Supabase mock that records insert payloads and echoes them (or returned_rows)."""
    captured: list[list[dict]] = []
    supabase = MagicMock()

    def capture_insert(rows):
        captured.append(rows)
        chain = MagicMock()
        chain.execute.return_value = MagicMock(
            data=rows if returned_rows is None else returned_rows
        )
        return chain

    supabase.table.return_value.insert.side_effect = capture_insert
    return supabase, captured


class TestStoreRecommendations:
    def test_stores_all_recommendations_with_string_field_ids(self):
        recs = [
            _make_rec(
                FIELD_ID_A, "340", "Cover Crops", "Improves soil health significantly.", "high"
            ),
            _make_rec(
                FIELD_ID_B, "329", "No-Till", "Reduces erosion and improves carbon.", "medium"
            ),
        ]
        supabase, captured = _capturing_supabase()

        result = _store_recommendations(supabase, recs, FARM_ID, status="pending")

        supabase.table.assert_called_once_with("recommendations")
        assert captured == [[
            {"field_id": FIELD_ID_A, "practice_code": "340", "title": "Cover Crops",
             "rationale": "Improves soil health significantly.", "priority": "high",
             "status": "pending"},
            {"field_id": FIELD_ID_B, "practice_code": "329", "title": "No-Till",
             "rationale": "Reduces erosion and improves carbon.", "priority": "medium",
             "status": "pending"},
        ]]
        assert all(isinstance(row["field_id"], str) for row in captured[0])
        assert result == captured[0]

    def test_empty_recommendations_returns_empty_without_db_call(self):
        supabase = MagicMock()
        assert _store_recommendations(supabase, [], FARM_ID) == []
        supabase.table.assert_not_called()

    def test_insert_failure_raises(self, caplog):
        """A failed insert must not be reported as zero recommendations."""
        supabase = MagicMock()
        supabase.table.return_value.insert.return_value.execute.side_effect = APIError(
            {"message": "insert denied", "code": "42501"}
        )

        with pytest.raises(APIError):
            _store_recommendations(supabase, [_make_rec()], FARM_ID)

        assert FARM_ID in caplog.text

    def test_insert_returns_none_data_returns_empty(self):
        supabase, _ = _capturing_supabase(returned_rows=None)
        supabase.table.return_value.insert.side_effect = None
        supabase.table.return_value.insert.return_value.execute.return_value = MagicMock(
            data=None
        )
        assert _store_recommendations(supabase, [_make_rec()], FARM_ID) == []


# ---------------------------------------------------------------------------
# Hallucination guard integration
# ---------------------------------------------------------------------------

class TestHallucinationGuard:
    def test_invalid_practice_code_flagged(self):
        recs = [_make_rec(FIELD_ID_A, "340"), _make_rec(FIELD_ID_A, "FAKE-CODE-9999")]
        valid, flagged = validate_practice_codes(recs, {"340", "329"})
        assert [r.practice_code for r in valid] == ["340"]
        assert [r.practice_code for r in flagged] == ["FAKE-CODE-9999"]

    def test_hallucinated_field_id_flagged(self):
        recs = [_make_rec(FIELD_ID_A), _make_rec(UNKNOWN_FIELD_ID)]
        valid, flagged = validate_field_ids(recs, {FIELD_ID_A})
        assert [str(r.field_id) for r in valid] == [FIELD_ID_A]
        assert [str(r.field_id) for r in flagged] == [UNKNOWN_FIELD_ID]

    def test_uppercase_field_id_matches_canonical_form(self):
        valid, flagged = validate_field_ids([_make_rec(FIELD_ID_A.upper())], {FIELD_ID_A})
        assert len(valid) == 1
        assert flagged == []


# ---------------------------------------------------------------------------
# generate_recommendations (integration)
# ---------------------------------------------------------------------------

def _pipeline_context(eqip_codes: list[str]) -> dict:
    """A context dict with the full shape returned by assemble_farm_context()."""
    return {
        "farm": {
            "id": FARM_ID,
            "name": "Test Farm",
            "state": "IA",
            "county_fips": "19153",
            "total_acres": 100.0,
            "goals": None,
        },
        "fields": [
            {
                "id": FIELD_ID_A,
                "name": "Field A",
                "acres": 100.0,
                "crop_type": "corn",
                "practices": [],
            }
        ],
        "soil_profiles": [],
        "weather": [],
        "current_practices": [],
        "acted_recommendations": [],
        "eqip_practices": [{"code": code, "name": f"Practice {code}"} for code in eqip_codes],
        "csp_assessment": None,
        "data_warnings": [],
    }


def _patch_context(context=None, **kwargs):
    return patch(
        "app.services.recommendations.assemble_farm_context",
        new=AsyncMock(return_value=context, **kwargs),
    )


def _patch_llm(**kwargs):
    return patch("app.services.recommendations._call_llm", new=AsyncMock(**kwargs))


@pytest.mark.asyncio
class TestGenerateRecommendations:
    async def test_no_fields_returns_empty_list_without_calling_llm(self):
        context = {**_pipeline_context(["340"]), "fields": []}

        with _patch_context(context), _patch_llm(return_value="[]") as llm:
            result = await generate_recommendations(FARM_ID, MagicMock())

        assert result == []
        llm.assert_not_awaited()

    async def test_context_value_error_propagates(self):
        with _patch_context(side_effect=ValueError("Farm not found")):
            with pytest.raises(ValueError, match="Farm not found"):
                await generate_recommendations(FARM_ID, MagicMock())

    async def test_empty_llm_output_on_every_attempt_raises(self):
        with (
            _patch_context(_pipeline_context(["340"])),
            _patch_llm(return_value=None) as llm,
        ):
            with pytest.raises(RecommendationOutputError):
                await generate_recommendations(FARM_ID, MagicMock())

        assert llm.await_count == 2

    async def test_malformed_output_on_every_attempt_raises(self):
        supabase = MagicMock()
        with (
            _patch_context(_pipeline_context(["340"])),
            _patch_llm(return_value="Here you go: [not json]") as llm,
        ):
            with pytest.raises(RecommendationOutputError):
                await generate_recommendations(FARM_ID, supabase)

        assert llm.await_count == 2
        supabase.table.assert_not_called()

    async def test_malformed_output_retried_once_then_succeeds(self):
        good = f'[{{"field_id": "{FIELD_ID_A}", "practice_code": "340", "title": "Cover", ' \
            '"rationale": "Low organic matter supports cover crops.", "priority": "high"}]'
        supabase, captured = _capturing_supabase()

        with (
            _patch_context(_pipeline_context(["340"])),
            _patch_llm(side_effect=["Sorry, prose only", good]) as llm,
        ):
            result = await generate_recommendations(FARM_ID, supabase)

        assert llm.await_count == 2
        assert [row["practice_code"] for row in result] == ["340"]
        assert captured[0][0]["field_id"] == FIELD_ID_A

    async def test_llm_error_propagates_without_retry(self):
        with (
            _patch_context(_pipeline_context(["340"])),
            _patch_llm(side_effect=_status_error(openai.RateLimitError, 429)) as llm,
        ):
            with pytest.raises(openai.RateLimitError):
                await generate_recommendations(FARM_ID, MagicMock())

        assert llm.await_count == 1

    async def test_valid_pipeline_stores_verified_and_drops_unverified(self):
        llm_json = (
            "[" + ",".join([
                '{"field_id": "%s", "practice_code": "340", "title": "Plant Cover Crops",'
                ' "rationale": "Cover crops improve soil health and water retention.",'
                ' "priority": "high", "csp_impact": "Addresses soil health."}' % FIELD_ID_A,
                '{"field_id": "%s", "practice_code": "999", "title": "Invented",'
                ' "rationale": "This practice code does not exist.", "priority": "low"}'
                % FIELD_ID_A,
                '{"field_id": "%s", "practice_code": "340", "title": "Other farm",'
                ' "rationale": "Targets a field outside this farm.", "priority": "low"}'
                % UNKNOWN_FIELD_ID,
            ]) + "]"
        )
        supabase, captured = _capturing_supabase()

        with _patch_context(_pipeline_context(["340", "329"])), _patch_llm(
            return_value=llm_json
        ):
            result = await generate_recommendations(FARM_ID, supabase)

        assert captured == [[{
            "field_id": FIELD_ID_A,
            "practice_code": "340",
            "title": "Plant Cover Crops",
            "rationale": "Cover crops improve soil health and water retention.",
            "priority": "high",
            "status": "pending",
        }]]
        assert result == captured[0]

    async def test_real_llm_client_error_propagates_through_pipeline(self):
        """The mocked SDK client raising must surface from the service, not return []."""
        client = _mock_client(side_effect=_connection_error())

        with (
            _patch_context(_pipeline_context(["340"])),
            patch(_PATCH_LLM_CLIENT, client),
        ):
            with pytest.raises(openai.APIConnectionError):
                await generate_recommendations(FARM_ID, MagicMock())


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

_VALID_UUID = "3f1c2b1e-8a4d-4c1e-9b2a-6d7e8f901234"


@pytest.fixture
def router_client():
    """TestClient with auth + Supabase dependencies overridden."""
    from fastapi.testclient import TestClient

    from app.auth.middleware import get_authenticated_client, get_current_user
    from app.main import app

    mock_supabase = MagicMock()
    app.dependency_overrides[get_current_user] = lambda: MagicMock(id="user-1")
    app.dependency_overrides[get_authenticated_client] = lambda: mock_supabase
    try:
        yield TestClient(app), mock_supabase
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_authenticated_client, None)


def _farm_visible(mock_supabase, visible: bool = True) -> None:
    farms_chain = mock_supabase.table.return_value.select.return_value.eq.return_value
    farms_chain.limit.return_value.execute.return_value = MagicMock(
        data=[{"id": _VALID_UUID}] if visible else []
    )


class TestRecommendationsRouterUUIDs:
    def test_list_non_uuid_field_id_returns_422(self, router_client):
        client, _ = router_client
        response = client.get("/api/v1/recommendations/?field_id=not-a-uuid")
        assert response.status_code == 422

    def test_list_valid_uuid_passes_str_to_supabase(self, router_client):
        client, mock_supabase = router_client
        chain = mock_supabase.table.return_value.select.return_value
        chain.eq.return_value.limit.return_value.execute.return_value = MagicMock(
            data=[{"id": _VALID_UUID}]
        )
        chain.eq.return_value.order.return_value.execute.return_value = MagicMock(data=[])

        response = client.get(f"/api/v1/recommendations/?field_id={_VALID_UUID}")

        assert response.status_code == 200
        assert response.json() == []
        assert [c.args for c in chain.eq.call_args_list] == [
            ("id", _VALID_UUID),
            ("field_id", _VALID_UUID),
        ]

    def test_list_hidden_field_returns_404_without_listing(self, router_client):
        """A field that is missing or hidden by RLS is a 404, not an empty list."""
        client, mock_supabase = router_client
        chain = mock_supabase.table.return_value.select.return_value
        chain.eq.return_value.limit.return_value.execute.return_value = MagicMock(data=[])

        response = client.get(f"/api/v1/recommendations/?field_id={_VALID_UUID}")

        assert response.status_code == 404
        chain.eq.return_value.order.assert_not_called()

    def test_update_status_non_uuid_id_returns_422(self, router_client):
        client, _ = router_client
        response = client.patch(
            "/api/v1/recommendations/not-a-uuid/status", json={"status": "acted"}
        )
        assert response.status_code == 422

    def test_update_status_not_found_returns_404(self, router_client):
        client, mock_supabase = router_client
        update_chain = mock_supabase.table.return_value.update.return_value
        update_chain.eq.return_value.execute.return_value = MagicMock(data=[])

        response = client.patch(
            f"/api/v1/recommendations/{_VALID_UUID}/status", json={"status": "acted"}
        )

        assert response.status_code == 404
        update_chain.eq.assert_called_once_with("id", _VALID_UUID)

    def test_generate_non_uuid_farm_id_returns_422(self, router_client):
        client, _ = router_client
        response = client.post("/api/v1/recommendations/generate?farm_id=not-a-uuid")
        assert response.status_code == 422

    def test_generate_valid_uuid_passes_str_to_service(self, router_client):
        client, mock_supabase = router_client
        _farm_visible(mock_supabase)
        stored = [{
            "id": "rec-1", "field_id": FIELD_ID_A, "practice_code": "340",
            "title": "Plant Cover Crops", "priority": "high", "status": "pending",
            "rationale": "not returned in the summary",
        }]
        run_mock = AsyncMock(return_value=stored)

        with patch("app.routers.recommendations.run_generation", new=run_mock):
            response = client.post(f"/api/v1/recommendations/generate?farm_id={_VALID_UUID}")

        assert response.status_code == 202
        assert response.json() == {
            "status": "generation_complete",
            "farm_id": _VALID_UUID,
            "recommendations_count": 1,
            "recommendations": [{
                "id": "rec-1", "field_id": FIELD_ID_A, "practice_code": "340",
                "title": "Plant Cover Crops", "priority": "high", "status": "pending",
            }],
        }
        passed_farm_id = run_mock.await_args.args[0]
        assert isinstance(passed_farm_id, str)
        assert passed_farm_id == _VALID_UUID

    def test_generate_hidden_farm_returns_404_without_generation(self, router_client):
        client, mock_supabase = router_client
        _farm_visible(mock_supabase, visible=False)
        run_mock = AsyncMock(return_value=[])

        with patch("app.routers.recommendations.run_generation", new=run_mock):
            response = client.post(f"/api/v1/recommendations/generate?farm_id={_VALID_UUID}")

        assert response.status_code == 404
        run_mock.assert_not_awaited()


class TestGenerateErrorMapping:
    @pytest.mark.parametrize(
        ("error", "status_code", "detail_fragment"),
        [
            (ValueError("Farm not found"), 404, "Farm not found"),
            (_connection_error(), 503, "temporarily unavailable"),
            (_timeout_error(), 503, "temporarily unavailable"),
            (_status_error(openai.RateLimitError, 429), 503, "busy"),
            (_status_error(openai.InternalServerError, 500), 502, "returned an error"),
            (_status_error(openai.APIStatusError, 402), 502, "returned an error"),
            (RecommendationOutputError("bad output"), 502, "unusable response"),
            (APIError({"message": "insert failed", "code": "500"}), 500, "could not be saved"),
        ],
        ids=[
            "not_found",
            "connection",
            "timeout",
            "rate_limit",
            "status",
            "insufficient_balance",
            "bad_output",
            "db",
        ],
    )
    def test_service_errors_map_to_status_codes(
        self, router_client, error, status_code, detail_fragment
    ):
        client, mock_supabase = router_client
        _farm_visible(mock_supabase)

        with patch(
            "app.routers.recommendations.run_generation",
            new=AsyncMock(side_effect=error),
        ):
            response = client.post(f"/api/v1/recommendations/generate?farm_id={_VALID_UUID}")

        assert response.status_code == status_code
        assert detail_fragment in response.json()["detail"]

    def test_llm_client_error_reaches_router_as_503(self, router_client):
        """End to end through the real service: a mocked SDK failure is not a 202."""
        client, mock_supabase = router_client
        _farm_visible(mock_supabase)
        llm_client = _mock_client(side_effect=_connection_error())

        with (
            _patch_context(_pipeline_context(["340"])),
            patch(_PATCH_LLM_CLIENT, llm_client),
        ):
            response = client.post(f"/api/v1/recommendations/generate?farm_id={_VALID_UUID}")

        assert response.status_code == 503
