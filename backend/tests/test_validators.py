"""
Tests for app.services.validators — LLM output validation and hallucination guard.
"""

from uuid import UUID

import pytest
from pydantic import ValidationError

from app.services.validators import (
    LLMPriority,
    LLMRecommendation,
    validate_field_ids,
    validate_practice_codes,
)

# field_id is validated as a UUID, so the conftest placeholder ids do not apply here.
FIELD_ID_A = "1a2b3c4d-5e6f-4a7b-8c9d-0e1f2a3b4c5d"
FIELD_ID_B = "2b3c4d5e-6f7a-4b8c-9d0e-1f2a3b4c5d6e"
UNKNOWN_FIELD_ID = "9f8e7d6c-5b4a-4938-8271-605f4e3d2c1b"


# ---------------------------------------------------------------------------
# Test data helpers
# ---------------------------------------------------------------------------

def _valid_raw(
    field_id: str = FIELD_ID_A,
    practice_code: str = "340",
    title: str = "Plant Cover Crops",
    rationale: str = "Cover crops significantly improve soil health and water retention.",
    priority: str = "high",
) -> dict:
    return {
        "field_id": field_id,
        "practice_code": practice_code,
        "title": title,
        "rationale": rationale,
        "priority": priority,
    }


def _make_rec(field_id=FIELD_ID_A, practice_code="340", priority="medium") -> LLMRecommendation:
    return LLMRecommendation(
        field_id=field_id,
        practice_code=practice_code,
        title="Test Recommendation",
        rationale="This is a valid rationale with enough detail.",
        priority=LLMPriority(priority),
    )


# ---------------------------------------------------------------------------
# LLMRecommendation — valid construction
# ---------------------------------------------------------------------------

class TestLLMRecommendationValid:
    def test_all_required_fields_creates_instance(self):
        rec = LLMRecommendation.model_validate(_valid_raw())

        assert rec.field_id == UUID(FIELD_ID_A)
        assert rec.practice_code == "340"
        assert rec.title == "Plant Cover Crops"
        assert rec.priority == LLMPriority.high
        assert rec.csp_impact is None

    def test_csp_impact_accepted(self):
        rec = LLMRecommendation.model_validate({**_valid_raw(), "csp_impact": "Soil health."})
        assert rec.csp_impact == "Soil health."

    @pytest.mark.parametrize("priority", ["high", "medium", "low"])
    def test_priority_values_accepted(self, priority):
        rec = LLMRecommendation.model_validate(_valid_raw(priority=priority))
        assert rec.priority == LLMPriority(priority)

    def test_default_priority_is_medium(self):
        raw = {k: v for k, v in _valid_raw().items() if k != "priority"}
        rec = LLMRecommendation.model_validate(raw)
        assert rec.priority == LLMPriority.medium

    def test_uppercase_field_id_normalized_to_canonical_string(self):
        rec = LLMRecommendation.model_validate(_valid_raw(field_id=FIELD_ID_A.upper()))
        assert str(rec.field_id) == FIELD_ID_A

    def test_practice_code_whitespace_stripped(self):
        rec = LLMRecommendation.model_validate(_valid_raw(practice_code="  340  "))
        assert rec.practice_code == "340"

    def test_title_whitespace_stripped(self):
        rec = LLMRecommendation.model_validate(_valid_raw(title="  Plant Cover Crops  "))
        assert rec.title == "Plant Cover Crops"


# ---------------------------------------------------------------------------
# LLMRecommendation — invalid construction
# ---------------------------------------------------------------------------

class TestLLMRecommendationInvalid:
    @pytest.mark.parametrize("missing", ["field_id", "practice_code", "title", "rationale"])
    def test_missing_required_field_raises(self, missing):
        raw = {k: v for k, v in _valid_raw().items() if k != missing}
        with pytest.raises(ValidationError):
            LLMRecommendation.model_validate(raw)

    def test_extra_fields_rejected(self):
        """LLM output is untrusted: keys we did not ask for fail validation."""
        raw = {**_valid_raw(), "llm_internal_notes": "thinking out loud"}
        with pytest.raises(ValidationError, match="llm_internal_notes"):
            LLMRecommendation.model_validate(raw)

    @pytest.mark.parametrize("field_id", ["", "field-uuid-aaaa", None, "12345"])
    def test_non_uuid_field_id_raises(self, field_id):
        with pytest.raises(ValidationError):
            LLMRecommendation.model_validate({**_valid_raw(), "field_id": field_id})

    def test_empty_practice_code_raises(self):
        with pytest.raises(ValidationError):
            LLMRecommendation.model_validate(_valid_raw(practice_code=""))

    def test_empty_title_raises(self):
        with pytest.raises(ValidationError):
            LLMRecommendation.model_validate(_valid_raw(title=""))

    def test_rationale_too_short_raises(self):
        with pytest.raises(ValidationError):
            LLMRecommendation.model_validate(_valid_raw(rationale="Short."))

    def test_title_exceeds_max_length_raises(self):
        with pytest.raises(ValidationError):
            LLMRecommendation.model_validate(_valid_raw(title="x" * 201))

    def test_invalid_priority_value_raises(self):
        with pytest.raises(ValidationError):
            LLMRecommendation.model_validate(_valid_raw(priority="urgent"))


# ---------------------------------------------------------------------------
# validate_practice_codes
# ---------------------------------------------------------------------------

class TestValidatePracticeCodes:
    def test_all_valid_codes_pass(self):
        recs = [_make_rec(practice_code="340"), _make_rec(practice_code="329")]
        valid, flagged = validate_practice_codes(recs, {"340", "329", "590"})
        assert valid == recs
        assert flagged == []

    def test_unknown_code_is_flagged(self):
        recs = [_make_rec(practice_code="340"), _make_rec(practice_code="HALLUCINATED-9999")]
        valid, flagged = validate_practice_codes(recs, {"340"})
        assert [r.practice_code for r in valid] == ["340"]
        assert [r.practice_code for r in flagged] == ["HALLUCINATED-9999"]

    def test_empty_valid_codes_set_all_flagged(self):
        recs = [_make_rec(practice_code="340")]
        valid, flagged = validate_practice_codes(recs, set())
        assert valid == []
        assert flagged == recs

    def test_empty_recommendations_both_lists_empty(self):
        assert validate_practice_codes([], {"340"}) == ([], [])

    def test_valid_recs_retain_original_data(self):
        rec = _make_rec(practice_code="340")
        valid, _ = validate_practice_codes([rec], {"340"})
        assert valid[0] is rec

    def test_mixed_valid_and_invalid_correctly_separated(self):
        recs = [
            _make_rec(FIELD_ID_A, "340"),
            _make_rec(FIELD_ID_A, "FAKE1"),
            _make_rec(FIELD_ID_B, "329"),
            _make_rec(FIELD_ID_B, "FAKE2"),
        ]
        valid, flagged = validate_practice_codes(recs, {"340", "329"})
        assert {r.practice_code for r in valid} == {"340", "329"}
        assert {r.practice_code for r in flagged} == {"FAKE1", "FAKE2"}


# ---------------------------------------------------------------------------
# validate_field_ids
# ---------------------------------------------------------------------------

class TestValidateFieldIds:
    def test_all_valid_field_ids_pass(self):
        recs = [_make_rec(FIELD_ID_A), _make_rec(FIELD_ID_B)]
        valid, flagged = validate_field_ids(recs, {FIELD_ID_A, FIELD_ID_B})
        assert valid == recs
        assert flagged == []

    def test_hallucinated_field_id_flagged(self):
        recs = [_make_rec(FIELD_ID_A), _make_rec(UNKNOWN_FIELD_ID)]
        valid, flagged = validate_field_ids(recs, {FIELD_ID_A})
        assert [str(r.field_id) for r in valid] == [FIELD_ID_A]
        assert [str(r.field_id) for r in flagged] == [UNKNOWN_FIELD_ID]

    def test_empty_valid_field_ids_all_flagged(self):
        recs = [_make_rec(FIELD_ID_A)]
        valid, flagged = validate_field_ids(recs, set())
        assert valid == []
        assert flagged == recs

    def test_empty_recommendations_both_lists_empty(self):
        assert validate_field_ids([], {FIELD_ID_A}) == ([], [])

    def test_valid_recs_retain_original_data(self):
        rec = _make_rec(FIELD_ID_A)
        valid, _ = validate_field_ids([rec], {FIELD_ID_A})
        assert valid[0] is rec


# ---------------------------------------------------------------------------
# End-to-end guard pipeline
# ---------------------------------------------------------------------------

class TestGuardPipeline:
    def test_field_id_guard_then_practice_code_guard(self):
        """Simulate the two-stage hallucination guard as used in generate_recommendations."""
        all_recs = [
            _make_rec(FIELD_ID_A, "340"),
            _make_rec(UNKNOWN_FIELD_ID, "329"),
            _make_rec(FIELD_ID_B, "HALLUCINATED-CODE"),
            _make_rec(FIELD_ID_A, "329"),
        ]

        after_field_guard, flagged_fields = validate_field_ids(
            all_recs, {FIELD_ID_A, FIELD_ID_B}
        )
        assert [str(r.field_id) for r in flagged_fields] == [UNKNOWN_FIELD_ID]

        final_valid, flagged_codes = validate_practice_codes(
            after_field_guard, {"340", "329", "590"}
        )
        assert [(str(r.field_id), r.practice_code) for r in final_valid] == [
            (FIELD_ID_A, "340"),
            (FIELD_ID_A, "329"),
        ]
        assert [r.practice_code for r in flagged_codes] == ["HALLUCINATED-CODE"]
