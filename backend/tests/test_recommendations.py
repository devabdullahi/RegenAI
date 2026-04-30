"""
Tests for app.services.recommendations — LLM recommendation pipeline.

Coverage targets:
  - _call_claude with a valid Anthropic response → returns raw text
  - _call_claude with no content blocks → returns None
  - _call_claude on APIConnectionError → returns None
  - _call_claude on RateLimitError → returns None
  - _call_claude on APIStatusError → returns None
  - _call_claude on generic Exception → returns None
  - _parse_llm_json with clean JSON array → parses correctly
  - _parse_llm_json with markdown code fence → strips fence and parses
  - _parse_llm_json with prose before array → finds array and parses
  - _parse_llm_json with invalid JSON → returns None
  - _parse_llm_json with no array brackets → returns None
  - _validate_recommendations with valid items → all pass
  - _validate_recommendations with invalid item → skipped, valid ones returned
  - _store_recommendations with valid recs → inserts rows and returns data
  - _store_recommendations with empty list → returns empty list (no DB call)
  - Hallucination guard via validate_practice_codes + validate_field_ids
  - generate_recommendations with no fields → empty list returned
  - generate_recommendations with empty Claude response → empty list
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from tests.conftest import make_supabase_mock, FARM_ID, FIELD_ID_A, FIELD_ID_B

import anthropic

from app.services.recommendations import (
    _call_claude,
    _parse_llm_json,
    _validate_recommendations,
    _store_recommendations,
)
from app.services.validators import (
    LLMRecommendation,
    LLMPriority,
    validate_practice_codes,
    validate_field_ids,
)


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


def _make_anthropic_response(text: str) -> MagicMock:
    """Build a fake Anthropic message response with one text content block."""
    block = MagicMock()
    block.text = text
    response = MagicMock()
    response.content = [block]
    response.stop_reason = "end_turn"
    return response


# ---------------------------------------------------------------------------
# _call_claude
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestCallClaude:
    async def test_valid_response_returns_text(self):
        """A successful Anthropic call should return the text from the response."""
        fake_response = _make_anthropic_response('[{"field_id": "abc"}]')

        mock_client = MagicMock()
        mock_client.messages.create = AsyncMock(return_value=fake_response)

        with patch("app.services.recommendations.anthropic.AsyncAnthropic", return_value=mock_client):
            result = await _call_claude("system prompt", "user message")

        assert result is not None
        assert '[{"field_id": "abc"}]' in result

    async def test_empty_content_blocks_returns_none(self):
        """When the Anthropic response has no text blocks, return None."""
        response = MagicMock()
        response.content = []  # no content blocks

        mock_client = MagicMock()
        mock_client.messages.create = AsyncMock(return_value=response)

        with patch("app.services.recommendations.anthropic.AsyncAnthropic", return_value=mock_client):
            result = await _call_claude("system", "user")

        assert result is None

    async def test_content_block_without_text_attribute_returns_none(self):
        """Content blocks without a text attribute should produce no output → None."""
        block = MagicMock(spec=[])  # no attributes at all
        response = MagicMock()
        response.content = [block]

        mock_client = MagicMock()
        mock_client.messages.create = AsyncMock(return_value=response)

        with patch("app.services.recommendations.anthropic.AsyncAnthropic", return_value=mock_client):
            result = await _call_claude("system", "user")

        assert result is None

    async def test_api_connection_error_returns_none(self):
        """APIConnectionError should be caught and None returned."""
        mock_client = MagicMock()
        mock_client.messages.create = AsyncMock(
            side_effect=anthropic.APIConnectionError(request=MagicMock())
        )

        with patch("app.services.recommendations.anthropic.AsyncAnthropic", return_value=mock_client):
            result = await _call_claude("system", "user")

        assert result is None

    async def test_rate_limit_error_returns_none(self):
        """RateLimitError should be caught and None returned."""
        mock_response = MagicMock()
        mock_response.status_code = 429

        mock_client = MagicMock()
        mock_client.messages.create = AsyncMock(
            side_effect=anthropic.RateLimitError(
                message="rate limited",
                response=mock_response,
                body={},
            )
        )

        with patch("app.services.recommendations.anthropic.AsyncAnthropic", return_value=mock_client):
            result = await _call_claude("system", "user")

        assert result is None

    async def test_api_status_error_returns_none(self):
        """APIStatusError (e.g. 500 from Anthropic) should be caught and None returned."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.headers = {}

        mock_client = MagicMock()
        mock_client.messages.create = AsyncMock(
            side_effect=anthropic.APIStatusError(
                message="internal error",
                response=mock_response,
                body={},
            )
        )

        with patch("app.services.recommendations.anthropic.AsyncAnthropic", return_value=mock_client):
            result = await _call_claude("system", "user")

        assert result is None

    async def test_generic_exception_returns_none(self):
        """Any unexpected exception should be caught and None returned."""
        mock_client = MagicMock()
        mock_client.messages.create = AsyncMock(side_effect=RuntimeError("something exploded"))

        with patch("app.services.recommendations.anthropic.AsyncAnthropic", return_value=mock_client):
            result = await _call_claude("system", "user")

        assert result is None

    async def test_multiple_text_blocks_joined(self):
        """Multiple text content blocks should be joined with newline."""
        block1 = MagicMock()
        block1.text = "part one"
        block2 = MagicMock()
        block2.text = "part two"
        response = MagicMock()
        response.content = [block1, block2]
        response.stop_reason = "end_turn"

        mock_client = MagicMock()
        mock_client.messages.create = AsyncMock(return_value=response)

        with patch("app.services.recommendations.anthropic.AsyncAnthropic", return_value=mock_client):
            result = await _call_claude("system", "user")

        assert "part one" in result
        assert "part two" in result


# ---------------------------------------------------------------------------
# _parse_llm_json
# ---------------------------------------------------------------------------

class TestParseLLMJson:
    def test_clean_json_array_parsed(self):
        """A plain JSON array string should be parsed into a list."""
        raw = '[{"field_id": "abc", "practice_code": "340"}]'
        result = _parse_llm_json(raw)
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["practice_code"] == "340"

    def test_markdown_code_fence_stripped(self):
        """A response wrapped in ```json ... ``` should be unwrapped and parsed."""
        raw = '```json\n[{"field_id": "abc"}]\n```'
        result = _parse_llm_json(raw)
        assert result is not None
        assert isinstance(result, list)

    def test_markdown_plain_fence_stripped(self):
        """A response wrapped in ``` ... ``` (no language tag) should also be unwrapped."""
        raw = '```\n[{"field_id": "xyz"}]\n```'
        result = _parse_llm_json(raw)
        assert result is not None
        assert result[0]["field_id"] == "xyz"

    def test_prose_before_array_ignored(self):
        """Leading prose before the JSON array should be stripped."""
        raw = 'Here are the recommendations:\n[{"practice_code": "329"}]'
        result = _parse_llm_json(raw)
        assert result is not None
        assert result[0]["practice_code"] == "329"

    def test_invalid_json_returns_none(self):
        """Malformed JSON that cannot be parsed should return None."""
        raw = "[{field_id: no quotes here}]"
        result = _parse_llm_json(raw)
        assert result is None

    def test_no_array_brackets_returns_none(self):
        """Output with no JSON array delimiters at all should return None."""
        raw = "I am unable to generate recommendations at this time."
        result = _parse_llm_json(raw)
        assert result is None

    def test_non_list_json_returns_none(self):
        """A valid JSON object (not array) should return None."""
        raw = '{"recommendations": []}'
        result = _parse_llm_json(raw)
        # A dict at top level is not a list → None
        assert result is None

    def test_empty_array_returns_empty_list(self):
        """An empty JSON array '[]' should return an empty list."""
        result = _parse_llm_json("[]")
        assert result == []

    def test_multiple_items_parsed(self):
        """Multiple recommendations in a single array should all be returned."""
        raw = '[{"field_id":"a","practice_code":"340"},{"field_id":"b","practice_code":"329"}]'
        result = _parse_llm_json(raw)
        assert len(result) == 2

    def test_whitespace_only_input_returns_none(self):
        """Pure whitespace input should return None (no array found)."""
        result = _parse_llm_json("   \n  ")
        assert result is None


# ---------------------------------------------------------------------------
# _validate_recommendations
# ---------------------------------------------------------------------------

class TestValidateRecommendations:
    def test_valid_items_all_pass(self):
        """All valid items should be returned in the validated list."""
        raw_list = [
            {
                "field_id": FIELD_ID_A,
                "practice_code": "340",
                "title": "Plant Cover Crops",
                "rationale": "Cover crops improve soil health significantly.",
                "priority": "high",
            },
            {
                "field_id": FIELD_ID_B,
                "practice_code": "329",
                "title": "Adopt No-Till",
                "rationale": "No-till reduces erosion and carbon emissions.",
                "priority": "medium",
            },
        ]
        result = _validate_recommendations(raw_list)
        assert len(result) == 2
        assert all(isinstance(r, LLMRecommendation) for r in result)

    def test_invalid_item_skipped_valid_returned(self):
        """Items that fail Pydantic validation should be skipped; valid ones kept."""
        raw_list = [
            {
                "field_id": FIELD_ID_A,
                "practice_code": "340",
                "title": "Valid Recommendation",
                "rationale": "Valid rationale text here.",
                "priority": "high",
            },
            {
                # Missing required 'field_id'
                "practice_code": "329",
                "title": "Missing field_id",
                "rationale": "This will fail validation.",
            },
        ]
        result = _validate_recommendations(raw_list)
        assert len(result) == 1
        assert result[0].practice_code == "340"

    def test_all_invalid_items_returns_empty(self):
        """When no items pass validation, an empty list is returned."""
        raw_list = [
            {"not": "a recommendation"},
            {"also": "wrong"},
        ]
        result = _validate_recommendations(raw_list)
        assert result == []

    def test_empty_list_returns_empty(self):
        """An empty input list should return an empty list."""
        result = _validate_recommendations([])
        assert result == []

    def test_practice_code_whitespace_stripped(self):
        """Whitespace around practice_code should be stripped by the validator."""
        raw_list = [
            {
                "field_id": FIELD_ID_A,
                "practice_code": "  340  ",
                "title": "Cover Crop",
                "rationale": "Important for soil health and erosion control.",
                "priority": "medium",
            }
        ]
        result = _validate_recommendations(raw_list)
        assert len(result) == 1
        assert result[0].practice_code == "340"

    def test_default_priority_medium_when_not_provided(self):
        """Priority should default to 'medium' when not specified."""
        raw_list = [
            {
                "field_id": FIELD_ID_A,
                "practice_code": "340",
                "title": "No Priority",
                "rationale": "Valid rationale string that is long enough.",
            }
        ]
        result = _validate_recommendations(raw_list)
        assert len(result) == 1
        assert result[0].priority == LLMPriority.medium


# ---------------------------------------------------------------------------
# _store_recommendations
# ---------------------------------------------------------------------------

class TestStoreRecommendations:
    def test_stores_all_recommendations(self):
        """All validated recommendations should be passed to a single insert call."""
        recs = [
            _make_rec(FIELD_ID_A, "340", "Cover Crops", "Improves soil health significantly.", "high"),
            _make_rec(FIELD_ID_B, "329", "No-Till", "Reduces erosion and improves carbon.", "medium"),
        ]

        stored_rows = [
            {"id": "rec-1", "field_id": FIELD_ID_A, "practice_code": "340",
             "title": "Cover Crops", "rationale": "Improves soil health significantly.",
             "priority": "high", "status": "pending"},
            {"id": "rec-2", "field_id": FIELD_ID_B, "practice_code": "329",
             "title": "No-Till", "rationale": "Reduces erosion and improves carbon.",
             "priority": "medium", "status": "pending"},
        ]

        mock_supabase = MagicMock()
        insert_chain = MagicMock()
        insert_chain.execute.return_value = MagicMock(data=stored_rows)
        mock_supabase.table.return_value.insert.return_value = insert_chain

        result = _store_recommendations(mock_supabase, recs, status="pending")

        assert len(result) == 2
        mock_supabase.table.assert_called_once_with("recommendations")

    def test_empty_recommendations_returns_empty_without_db_call(self):
        """When passed an empty list, no DB insert should occur."""
        mock_supabase = MagicMock()

        result = _store_recommendations(mock_supabase, [], status="pending")

        assert result == []
        mock_supabase.table.assert_not_called()

    def test_insert_failure_returns_empty_list(self):
        """A DB insert exception should be caught and an empty list returned."""
        recs = [_make_rec()]
        mock_supabase = MagicMock()
        mock_supabase.table.return_value.insert.side_effect = Exception("DB error")

        result = _store_recommendations(mock_supabase, recs, status="pending")

        assert result == []

    def test_insert_returns_none_data_returns_empty(self):
        """When insert returns no data, an empty list should be returned."""
        recs = [_make_rec()]
        mock_supabase = MagicMock()
        insert_chain = MagicMock()
        insert_chain.execute.return_value = MagicMock(data=None)
        mock_supabase.table.return_value.insert.return_value = insert_chain

        result = _store_recommendations(mock_supabase, recs, status="pending")

        assert result == []

    def test_stored_rows_include_correct_status(self):
        """The status passed to _store_recommendations should be on each row."""
        recs = [_make_rec()]
        captured_payloads: list[list[dict]] = []

        mock_supabase = MagicMock()

        def capture_insert(rows):
            captured_payloads.append(rows)
            chain = MagicMock()
            chain.execute.return_value = MagicMock(data=rows)
            return chain

        mock_supabase.table.return_value.insert.side_effect = capture_insert

        _store_recommendations(mock_supabase, recs, status="pending")

        assert len(captured_payloads) == 1
        assert captured_payloads[0][0]["status"] == "pending"


# ---------------------------------------------------------------------------
# Hallucination guard integration
# ---------------------------------------------------------------------------

class TestHallucinationGuard:
    def test_valid_practice_codes_pass(self):
        """Recommendations with codes in the valid set should all pass."""
        recs = [
            _make_rec(FIELD_ID_A, "340"),
            _make_rec(FIELD_ID_B, "329"),
        ]
        valid, flagged = validate_practice_codes(recs, {"340", "329", "590"})
        assert len(valid) == 2
        assert len(flagged) == 0

    def test_invalid_practice_code_flagged(self):
        """A practice code not in the valid set should be flagged."""
        recs = [
            _make_rec(FIELD_ID_A, "340"),
            _make_rec(FIELD_ID_A, "FAKE-CODE-9999"),
        ]
        valid, flagged = validate_practice_codes(recs, {"340", "329"})
        assert len(valid) == 1
        assert len(flagged) == 1
        assert flagged[0].practice_code == "FAKE-CODE-9999"

    def test_all_invalid_codes_all_flagged(self):
        """When no codes are in the valid set, all recommendations are flagged."""
        recs = [_make_rec(FIELD_ID_A, "XXX"), _make_rec(FIELD_ID_B, "YYY")]
        valid, flagged = validate_practice_codes(recs, {"340"})
        assert len(valid) == 0
        assert len(flagged) == 2

    def test_empty_valid_codes_set_all_flagged(self):
        """With an empty valid codes set, every recommendation is flagged."""
        recs = [_make_rec()]
        valid, flagged = validate_practice_codes(recs, set())
        assert len(valid) == 0
        assert len(flagged) == 1

    def test_valid_field_ids_pass(self):
        """Recommendations targeting known field IDs should all pass."""
        recs = [
            _make_rec(FIELD_ID_A),
            _make_rec(FIELD_ID_B),
        ]
        valid, flagged = validate_field_ids(recs, {FIELD_ID_A, FIELD_ID_B})
        assert len(valid) == 2
        assert len(flagged) == 0

    def test_hallucinated_field_id_flagged(self):
        """A field ID not belonging to the farm should be flagged."""
        recs = [
            _make_rec(FIELD_ID_A),
            _make_rec("hallucinated-field-uuid-9999"),
        ]
        valid, flagged = validate_field_ids(recs, {FIELD_ID_A})
        assert len(valid) == 1
        assert len(flagged) == 1
        assert flagged[0].field_id == "hallucinated-field-uuid-9999"

    def test_empty_valid_field_ids_all_flagged(self):
        """With an empty valid field IDs set, every recommendation is flagged."""
        recs = [_make_rec(FIELD_ID_A)]
        valid, flagged = validate_field_ids(recs, set())
        assert len(valid) == 0
        assert len(flagged) == 1


# ---------------------------------------------------------------------------
# generate_recommendations (integration)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestGenerateRecommendations:
    async def test_no_fields_returns_empty_list(self):
        """A farm with no fields should return an empty list without calling Claude."""
        from app.services.recommendations import generate_recommendations

        context_with_no_fields = {
            "farm": {"id": FARM_ID, "state": "IA"},
            "fields": [],
            "eqip_practices": [{"code": "340"}, {"code": "329"}],
        }

        mock_supabase = MagicMock()

        with patch(
            "app.services.recommendations.assemble_farm_context",
            new=AsyncMock(return_value=context_with_no_fields),
        ):
            result = await generate_recommendations(FARM_ID, mock_supabase)

        assert result == []

    async def test_context_assembly_failure_returns_empty_list(self):
        """If context assembly raises ValueError, the function returns an empty list."""
        from app.services.recommendations import generate_recommendations

        mock_supabase = MagicMock()

        with patch(
            "app.services.recommendations.assemble_farm_context",
            new=AsyncMock(side_effect=ValueError("Farm not found")),
        ):
            result = await generate_recommendations(FARM_ID, mock_supabase)

        assert result == []

    async def test_empty_claude_response_returns_empty_list(self):
        """When Claude returns None on both attempts, the function returns an empty list."""
        from app.services.recommendations import generate_recommendations

        context = {
            "farm": {"id": FARM_ID, "state": "IA"},
            "fields": [{"id": FIELD_ID_A, "name": "Field A", "acres": 100.0}],
            "eqip_practices": [{"code": "340"}],
        }
        mock_supabase = MagicMock()

        with (
            patch(
                "app.services.recommendations.assemble_farm_context",
                new=AsyncMock(return_value=context),
            ),
            patch(
                "app.services.recommendations._call_claude",
                new=AsyncMock(return_value=None),
            ),
        ):
            result = await generate_recommendations(FARM_ID, mock_supabase)

        assert result == []

    async def test_malformed_json_from_claude_returns_empty_list(self):
        """When Claude returns unparseable JSON on all attempts, return empty list."""
        from app.services.recommendations import generate_recommendations

        context = {
            "farm": {"id": FARM_ID, "state": "IA"},
            "fields": [{"id": FIELD_ID_A, "name": "Field A", "acres": 100.0}],
            "eqip_practices": [{"code": "340"}],
        }
        mock_supabase = MagicMock()

        with (
            patch(
                "app.services.recommendations.assemble_farm_context",
                new=AsyncMock(return_value=context),
            ),
            patch(
                "app.services.recommendations._call_claude",
                new=AsyncMock(return_value="not valid json at all"),
            ),
        ):
            result = await generate_recommendations(FARM_ID, mock_supabase)

        assert result == []

    async def test_valid_pipeline_stores_and_returns_recommendations(self):
        """The full pipeline with valid output should store and return recommendations."""
        from app.services.recommendations import generate_recommendations

        context = {
            "farm": {"id": FARM_ID, "state": "IA"},
            "fields": [{"id": FIELD_ID_A, "name": "Field A", "acres": 100.0}],
            "eqip_practices": [{"code": "340"}, {"code": "329"}],
        }

        claude_json = f"""[
            {{
                "field_id": "{FIELD_ID_A}",
                "practice_code": "340",
                "title": "Plant Cover Crops",
                "rationale": "Cover crops significantly improve soil health and water retention.",
                "priority": "high"
            }}
        ]"""

        stored_row = {
            "id": "new-rec-uuid",
            "field_id": FIELD_ID_A,
            "practice_code": "340",
            "title": "Plant Cover Crops",
            "rationale": "Cover crops significantly improve soil health and water retention.",
            "priority": "high",
            "status": "pending",
        }

        mock_supabase = MagicMock()
        insert_chain = MagicMock()
        insert_chain.execute.return_value = MagicMock(data=[stored_row])
        mock_supabase.table.return_value.insert.return_value = insert_chain

        with (
            patch(
                "app.services.recommendations.assemble_farm_context",
                new=AsyncMock(return_value=context),
            ),
            patch(
                "app.services.recommendations._call_claude",
                new=AsyncMock(return_value=claude_json),
            ),
        ):
            result = await generate_recommendations(FARM_ID, mock_supabase)

        assert len(result) == 1
        assert result[0]["practice_code"] == "340"
