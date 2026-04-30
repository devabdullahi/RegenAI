"""
Tests for app.services.validators — LLM output validation and hallucination guard.

Coverage targets:
  - LLMRecommendation with all required fields → parsed correctly
  - LLMRecommendation missing field_id → ValidationError
  - LLMRecommendation missing practice_code → ValidationError
  - LLMRecommendation missing title → ValidationError
  - LLMRecommendation with rationale too short → ValidationError
  - LLMRecommendation with title too long → ValidationError
  - LLMRecommendation with whitespace practice_code → stripped by validator
  - LLMRecommendation with whitespace title → stripped by validator
  - LLMRecommendation with invalid priority value → ValidationError
  - LLMRecommendation default priority → 'medium'
  - LLMRecommendationList validates list of recommendations
  - validate_practice_codes: all valid → empty flagged list
  - validate_practice_codes: unknown code → flagged
  - validate_practice_codes: empty valid_codes → all flagged
  - validate_practice_codes: empty recommendations → both lists empty
  - validate_field_ids: all valid → empty flagged list
  - validate_field_ids: unknown field_id → flagged
  - validate_field_ids: empty valid_field_ids → all flagged
  - validate_field_ids: empty recommendations → both lists empty
  - Extra fields in raw dict (from LLM) → tolerated, not crash (model_validate)
  - All priority values (high, medium, low) accepted
"""

import pytest
from pydantic import ValidationError
from tests.conftest import FIELD_ID_A, FIELD_ID_B

from app.services.validators import (
    LLMPriority,
    LLMRecommendation,
    LLMRecommendationList,
    validate_practice_codes,
    validate_field_ids,
)


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
        """A dict with all required fields should produce a valid LLMRecommendation."""
        raw = _valid_raw()
        rec = LLMRecommendation.model_validate(raw)

        assert rec.field_id == FIELD_ID_A
        assert rec.practice_code == "340"
        assert rec.title == "Plant Cover Crops"
        assert rec.priority == LLMPriority.high

    def test_model_validate_from_dict(self):
        """model_validate() with a valid dict should succeed."""
        rec = LLMRecommendation.model_validate(_valid_raw())
        assert rec.field_id == FIELD_ID_A

    def test_priority_high_accepted(self):
        """Priority value 'high' should be stored as LLMPriority.high."""
        rec = LLMRecommendation.model_validate(_valid_raw(priority="high"))
        assert rec.priority == LLMPriority.high

    def test_priority_medium_accepted(self):
        """Priority value 'medium' should be stored as LLMPriority.medium."""
        rec = LLMRecommendation.model_validate(_valid_raw(priority="medium"))
        assert rec.priority == LLMPriority.medium

    def test_priority_low_accepted(self):
        """Priority value 'low' should be stored as LLMPriority.low."""
        rec = LLMRecommendation.model_validate(_valid_raw(priority="low"))
        assert rec.priority == LLMPriority.low

    def test_default_priority_is_medium(self):
        """When priority is omitted, it should default to 'medium'."""
        raw = {k: v for k, v in _valid_raw().items() if k != "priority"}
        rec = LLMRecommendation.model_validate(raw)
        assert rec.priority == LLMPriority.medium

    def test_extra_fields_tolerated(self):
        """Extra keys from the LLM response should not raise a ValidationError."""
        raw = {
            **_valid_raw(),
            "unexpected_key": "some_extra_value",
            "llm_internal_notes": "thinking out loud",
        }
        # Pydantic v2 ignores extra fields by default
        rec = LLMRecommendation.model_validate(raw)
        assert rec.field_id == FIELD_ID_A

    def test_practice_code_whitespace_stripped(self):
        """Leading/trailing whitespace in practice_code should be stripped."""
        raw = _valid_raw(practice_code="  340  ")
        rec = LLMRecommendation.model_validate(raw)
        assert rec.practice_code == "340"

    def test_title_whitespace_stripped(self):
        """Leading/trailing whitespace in title should be stripped."""
        raw = _valid_raw(title="  Plant Cover Crops  ")
        rec = LLMRecommendation.model_validate(raw)
        assert rec.title == "Plant Cover Crops"


# ---------------------------------------------------------------------------
# LLMRecommendation — invalid construction (missing required fields)
# ---------------------------------------------------------------------------

class TestLLMRecommendationInvalid:
    def test_missing_field_id_raises_validation_error(self):
        """Omitting field_id must raise ValidationError."""
        raw = {k: v for k, v in _valid_raw().items() if k != "field_id"}
        with pytest.raises(ValidationError):
            LLMRecommendation.model_validate(raw)

    def test_missing_practice_code_raises_validation_error(self):
        """Omitting practice_code must raise ValidationError."""
        raw = {k: v for k, v in _valid_raw().items() if k != "practice_code"}
        with pytest.raises(ValidationError):
            LLMRecommendation.model_validate(raw)

    def test_missing_title_raises_validation_error(self):
        """Omitting title must raise ValidationError."""
        raw = {k: v for k, v in _valid_raw().items() if k != "title"}
        with pytest.raises(ValidationError):
            LLMRecommendation.model_validate(raw)

    def test_missing_rationale_raises_validation_error(self):
        """Omitting rationale must raise ValidationError."""
        raw = {k: v for k, v in _valid_raw().items() if k != "rationale"}
        with pytest.raises(ValidationError):
            LLMRecommendation.model_validate(raw)

    def test_empty_field_id_raises_validation_error(self):
        """An empty string for field_id (min_length=1) must raise ValidationError."""
        raw = _valid_raw(field_id="")
        with pytest.raises(ValidationError):
            LLMRecommendation.model_validate(raw)

    def test_empty_practice_code_raises_validation_error(self):
        """An empty string for practice_code (min_length=1) must raise ValidationError."""
        raw = _valid_raw(practice_code="")
        with pytest.raises(ValidationError):
            LLMRecommendation.model_validate(raw)

    def test_empty_title_raises_validation_error(self):
        """An empty string for title (min_length=1) must raise ValidationError."""
        raw = _valid_raw(title="")
        with pytest.raises(ValidationError):
            LLMRecommendation.model_validate(raw)

    def test_rationale_too_short_raises_validation_error(self):
        """rationale with fewer than 10 characters must raise ValidationError."""
        raw = _valid_raw(rationale="Short.")  # 6 chars < min_length=10
        with pytest.raises(ValidationError):
            LLMRecommendation.model_validate(raw)

    def test_title_exceeds_max_length_raises_validation_error(self):
        """title longer than 200 characters must raise ValidationError."""
        raw = _valid_raw(title="x" * 201)
        with pytest.raises(ValidationError):
            LLMRecommendation.model_validate(raw)

    def test_invalid_priority_value_raises_validation_error(self):
        """An unrecognised priority value must raise ValidationError."""
        raw = _valid_raw(priority="urgent")
        with pytest.raises(ValidationError):
            LLMRecommendation.model_validate(raw)

    def test_none_field_id_raises_validation_error(self):
        """None is not a valid string for field_id."""
        raw = {**_valid_raw(), "field_id": None}
        with pytest.raises(ValidationError):
            LLMRecommendation.model_validate(raw)


# ---------------------------------------------------------------------------
# LLMRecommendationList
# ---------------------------------------------------------------------------

class TestLLMRecommendationList:
    def test_valid_list_of_recommendations(self):
        """A list of valid recommendation dicts should be accepted."""
        recs = [_valid_raw(), _valid_raw(field_id=FIELD_ID_B, practice_code="329")]
        obj = LLMRecommendationList(recommendations=[
            LLMRecommendation.model_validate(r) for r in recs
        ])
        assert len(obj.recommendations) == 2

    def test_empty_list_accepted(self):
        """An empty recommendations list should be valid."""
        obj = LLMRecommendationList(recommendations=[])
        assert obj.recommendations == []

    def test_list_missing_recommendations_key_raises(self):
        """Constructing LLMRecommendationList without 'recommendations' must raise."""
        with pytest.raises(ValidationError):
            LLMRecommendationList()


# ---------------------------------------------------------------------------
# validate_practice_codes
# ---------------------------------------------------------------------------

class TestValidatePracticeCodes:
    def test_all_valid_codes_pass(self):
        """All codes in the valid set should pass; flagged list should be empty."""
        recs = [_make_rec(practice_code="340"), _make_rec(practice_code="329")]
        valid, flagged = validate_practice_codes(recs, {"340", "329", "590"})

        assert len(valid) == 2
        assert len(flagged) == 0

    def test_unknown_code_is_flagged(self):
        """A practice_code not in the valid set should move to the flagged list."""
        recs = [
            _make_rec(practice_code="340"),
            _make_rec(practice_code="HALLUCINATED-9999"),
        ]
        valid, flagged = validate_practice_codes(recs, {"340"})

        assert len(valid) == 1
        assert len(flagged) == 1
        assert flagged[0].practice_code == "HALLUCINATED-9999"

    def test_all_unknown_codes_all_flagged(self):
        """When no codes match the valid set, all should be flagged."""
        recs = [_make_rec(practice_code="AAA"), _make_rec(practice_code="BBB")]
        valid, flagged = validate_practice_codes(recs, {"340", "329"})

        assert len(valid) == 0
        assert len(flagged) == 2

    def test_empty_valid_codes_set_all_flagged(self):
        """With an empty valid_codes set, every recommendation is flagged."""
        recs = [_make_rec(practice_code="340")]
        valid, flagged = validate_practice_codes(recs, set())

        assert len(valid) == 0
        assert len(flagged) == 1

    def test_empty_recommendations_both_lists_empty(self):
        """Empty recommendations input → empty valid and flagged lists."""
        valid, flagged = validate_practice_codes([], {"340"})
        assert valid == []
        assert flagged == []

    def test_returns_tuple_of_two_lists(self):
        """The return value must be a 2-tuple of lists."""
        result = validate_practice_codes([], set())
        assert isinstance(result, tuple)
        assert len(result) == 2
        valid, flagged = result
        assert isinstance(valid, list)
        assert isinstance(flagged, list)

    def test_valid_recs_retain_original_data(self):
        """The returned valid recommendation objects must be the original instances."""
        rec = _make_rec(practice_code="340")
        valid, _ = validate_practice_codes([rec], {"340"})
        assert valid[0] is rec

    def test_mixed_valid_and_invalid_correctly_separated(self):
        """Multiple valid and invalid codes should be cleanly separated."""
        recs = [
            _make_rec(FIELD_ID_A, "340"),   # valid
            _make_rec(FIELD_ID_A, "FAKE1"), # invalid
            _make_rec(FIELD_ID_B, "329"),   # valid
            _make_rec(FIELD_ID_B, "FAKE2"), # invalid
        ]
        valid, flagged = validate_practice_codes(recs, {"340", "329"})

        assert {r.practice_code for r in valid} == {"340", "329"}
        assert {r.practice_code for r in flagged} == {"FAKE1", "FAKE2"}


# ---------------------------------------------------------------------------
# validate_field_ids
# ---------------------------------------------------------------------------

class TestValidateFieldIds:
    def test_all_valid_field_ids_pass(self):
        """Field IDs in the valid set should all pass."""
        recs = [_make_rec(FIELD_ID_A), _make_rec(FIELD_ID_B)]
        valid, flagged = validate_field_ids(recs, {FIELD_ID_A, FIELD_ID_B})

        assert len(valid) == 2
        assert len(flagged) == 0

    def test_hallucinated_field_id_flagged(self):
        """A field_id not in the valid set should be flagged."""
        hallucinated_id = "00000000-0000-0000-0000-hallucinated"
        recs = [
            _make_rec(FIELD_ID_A),
            _make_rec(hallucinated_id),
        ]
        valid, flagged = validate_field_ids(recs, {FIELD_ID_A})

        assert len(valid) == 1
        assert len(flagged) == 1
        assert flagged[0].field_id == hallucinated_id

    def test_empty_valid_field_ids_all_flagged(self):
        """With an empty valid_field_ids set, every recommendation is flagged."""
        recs = [_make_rec(FIELD_ID_A)]
        valid, flagged = validate_field_ids(recs, set())

        assert len(valid) == 0
        assert len(flagged) == 1

    def test_empty_recommendations_both_lists_empty(self):
        """Empty recommendations input → empty valid and flagged lists."""
        valid, flagged = validate_field_ids([], {FIELD_ID_A})
        assert valid == []
        assert flagged == []

    def test_returns_tuple_of_two_lists(self):
        """The return value must be a 2-tuple of lists."""
        result = validate_field_ids([], set())
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_all_same_field_id_valid(self):
        """Multiple recommendations for the same valid field should all pass."""
        recs = [_make_rec(FIELD_ID_A), _make_rec(FIELD_ID_A), _make_rec(FIELD_ID_A)]
        valid, flagged = validate_field_ids(recs, {FIELD_ID_A})

        assert len(valid) == 3
        assert len(flagged) == 0

    def test_all_invalid_field_ids_all_flagged(self):
        """When no field IDs belong to the farm, all should be flagged."""
        recs = [
            _make_rec("other-farm-field-1"),
            _make_rec("other-farm-field-2"),
        ]
        valid, flagged = validate_field_ids(recs, {FIELD_ID_A, FIELD_ID_B})

        assert len(valid) == 0
        assert len(flagged) == 2

    def test_valid_recs_retain_original_data(self):
        """The returned valid recommendation objects must be the original instances."""
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
            _make_rec(FIELD_ID_A, "340"),               # valid field, valid code
            _make_rec("unknown-field-id", "329"),        # invalid field, valid code
            _make_rec(FIELD_ID_B, "HALLUCINATED-CODE"),  # valid field, invalid code
            _make_rec(FIELD_ID_A, "329"),                # valid field, valid code
        ]

        # Stage 1: field ID guard
        after_field_guard, flagged_fields = validate_field_ids(
            all_recs, {FIELD_ID_A, FIELD_ID_B}
        )
        assert len(after_field_guard) == 3  # excludes "unknown-field-id"
        assert len(flagged_fields) == 1

        # Stage 2: practice code guard
        final_valid, flagged_codes = validate_practice_codes(
            after_field_guard, {"340", "329", "590"}
        )
        assert len(final_valid) == 2  # excludes "HALLUCINATED-CODE"
        assert len(flagged_codes) == 1
        assert flagged_codes[0].practice_code == "HALLUCINATED-CODE"

    def test_all_pass_through_both_guards(self):
        """Recommendations that pass both guards should end up fully valid."""
        recs = [
            _make_rec(FIELD_ID_A, "340"),
            _make_rec(FIELD_ID_B, "329"),
        ]
        after_field, _ = validate_field_ids(recs, {FIELD_ID_A, FIELD_ID_B})
        final, _ = validate_practice_codes(after_field, {"340", "329"})

        assert len(final) == 2

    def test_none_pass_through_either_guard(self):
        """Recs with invalid fields and codes should be fully filtered out."""
        recs = [
            _make_rec("bad-field", "FAKE"),
        ]
        after_field, flagged_field = validate_field_ids(recs, {FIELD_ID_A})
        assert len(after_field) == 0

        # Nothing left for the practice code guard
        final, flagged_code = validate_practice_codes(after_field, {"340"})
        assert len(final) == 0
        assert len(flagged_field) == 1
        assert len(flagged_code) == 0
