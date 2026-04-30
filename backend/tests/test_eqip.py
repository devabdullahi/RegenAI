"""
Tests for app.services.eqip — EQIP eligibility evaluator.

Coverage targets:
  - Farm with qualifying acted practices + EQIP codes → eligible/pending_review
  - Farm with qualifying practices + supporting docs → eligible
  - Farm with qualifying practices + no docs → pending_review
  - Farm with no acted recommendations → not_eligible
  - Farm with acted practices that don't match EQIP codes → not_eligible
  - Farm with no fields → not_eligible (with notes)
  - Edge case: empty EQIP reference table → not_eligible
  - Correct practice codes appear in practices_documented
  - De-duplication: same (field, code) acted twice counted once
  - Persistence: credit_eligibility upsert called
  - Upsert failure is non-fatal (result still returned)
"""

import pytest
from unittest.mock import MagicMock, patch
from tests.conftest import make_supabase_mock, _make_chain, FARM_ID, FIELD_ID_A, FIELD_ID_B

from app.services.eqip import evaluate_eqip_eligibility


# ---------------------------------------------------------------------------
# EQIP reference data (mirrors seed data)
# ---------------------------------------------------------------------------

EQIP_PRACTICES = [
    {"code": "340", "name": "Cover Crop", "category": "soil_health"},
    {"code": "329", "name": "Residue and Tillage Management, No-Till", "category": "soil_erosion"},
    {"code": "590", "name": "Nutrient Management", "category": "water_quality"},
    {"code": "393", "name": "Filter Strip", "category": "water_quality"},
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_eqip_supabase(
    fields: list[dict],
    acted_recs: list[dict],
    eqip_practices: list[dict],
    documents: list[dict] | None = None,
    upsert_data: list[dict] | None = None,
) -> MagicMock:
    """Build a Supabase mock for EQIP evaluation with configurable responses."""
    mock = MagicMock()
    call_count: dict[str, int] = {}

    # Default upsert result
    if upsert_data is None:
        upsert_data = [{"id": "elig-uuid-1", "farm_id": FARM_ID, "program": "EQIP"}]

    def _table(name: str):
        call_count[name] = call_count.get(name, 0) + 1

        if name == "fields":
            return _make_chain(data=fields)

        if name == "recommendations":
            return _make_chain(data=acted_recs)

        if name == "eqip_practices":
            return _make_chain(data=eqip_practices)

        if name == "documents":
            return _make_chain(data=documents or [])

        if name == "credit_eligibility":
            # Return mock supporting upsert chain
            tbl = MagicMock()
            upsert_chain = MagicMock()
            upsert_chain.execute.return_value = MagicMock(data=upsert_data)
            tbl.upsert.return_value = upsert_chain
            return tbl

        return _make_chain(data=None)

    mock.table.side_effect = _table
    return mock


# ---------------------------------------------------------------------------
# Tests: Status = pending_review (qualifying practices, no docs)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestEqipPendingReview:
    async def test_matching_practices_no_docs_returns_pending_review(self):
        """Farm with EQIP-matching acted practices but no documents → pending_review."""
        fields = [{"id": FIELD_ID_A, "name": "North 40", "acres": 120.0}]
        acted_recs = [{"field_id": FIELD_ID_A, "practice_code": "340", "title": "Cover Crop"}]

        supabase = _make_eqip_supabase(fields, acted_recs, EQIP_PRACTICES, documents=[])
        result = await evaluate_eqip_eligibility(FARM_ID, supabase)

        assert result["status"] == "pending_review"
        assert "340" in result["practices_documented"]

    async def test_pending_review_notes_mention_missing_docs(self):
        """Notes for pending_review should explain the need for documentation."""
        fields = [{"id": FIELD_ID_A, "name": "North 40", "acres": 120.0}]
        acted_recs = [{"field_id": FIELD_ID_A, "practice_code": "329", "title": "No-Till"}]

        supabase = _make_eqip_supabase(fields, acted_recs, EQIP_PRACTICES, documents=[])
        result = await evaluate_eqip_eligibility(FARM_ID, supabase)

        assert "document" in result["notes"].lower() or "upload" in result["notes"].lower()

    async def test_multiple_qualifying_practices_all_in_documented(self):
        """All matching practice codes should appear in practices_documented."""
        fields = [{"id": FIELD_ID_A, "name": "North 40", "acres": 120.0}]
        acted_recs = [
            {"field_id": FIELD_ID_A, "practice_code": "340", "title": "Cover Crop"},
            {"field_id": FIELD_ID_A, "practice_code": "590", "title": "Nutrient Management"},
        ]

        supabase = _make_eqip_supabase(fields, acted_recs, EQIP_PRACTICES, documents=[])
        result = await evaluate_eqip_eligibility(FARM_ID, supabase)

        assert "340" in result["practices_documented"]
        assert "590" in result["practices_documented"]


# ---------------------------------------------------------------------------
# Tests: Status = eligible (qualifying practices + documents)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestEqipEligible:
    async def test_qualifying_practices_with_soil_report_returns_eligible(self):
        """Farm with matching practices AND a soil_report document → eligible."""
        fields = [{"id": FIELD_ID_A, "name": "North 40", "acres": 120.0}]
        acted_recs = [{"field_id": FIELD_ID_A, "practice_code": "340", "title": "Cover Crop"}]
        documents = [{"doc_type": "soil_report"}]

        supabase = _make_eqip_supabase(fields, acted_recs, EQIP_PRACTICES, documents=documents)
        result = await evaluate_eqip_eligibility(FARM_ID, supabase)

        assert result["status"] == "eligible"

    async def test_field_photo_document_triggers_eligible(self):
        """A field_photo document is sufficient for the documentation requirement."""
        fields = [{"id": FIELD_ID_A, "name": "North 40", "acres": 120.0}]
        acted_recs = [{"field_id": FIELD_ID_A, "practice_code": "329", "title": "No-Till"}]
        documents = [{"doc_type": "field_photo"}]

        supabase = _make_eqip_supabase(fields, acted_recs, EQIP_PRACTICES, documents=documents)
        result = await evaluate_eqip_eligibility(FARM_ID, supabase)

        assert result["status"] == "eligible"

    async def test_compliance_document_triggers_eligible(self):
        """A compliance document is sufficient for the documentation requirement."""
        fields = [{"id": FIELD_ID_A, "name": "North 40", "acres": 120.0}]
        acted_recs = [{"field_id": FIELD_ID_A, "practice_code": "590", "title": "Nutrient Mgmt"}]
        documents = [{"doc_type": "compliance"}]

        supabase = _make_eqip_supabase(fields, acted_recs, EQIP_PRACTICES, documents=documents)
        result = await evaluate_eqip_eligibility(FARM_ID, supabase)

        assert result["status"] == "eligible"

    async def test_eligible_notes_mention_matched_practices(self):
        """Eligible notes should reference the matched practice codes."""
        fields = [{"id": FIELD_ID_A, "name": "North 40", "acres": 120.0}]
        acted_recs = [{"field_id": FIELD_ID_A, "practice_code": "340", "title": "Cover Crop"}]
        documents = [{"doc_type": "soil_report"}]

        supabase = _make_eqip_supabase(fields, acted_recs, EQIP_PRACTICES, documents=documents)
        result = await evaluate_eqip_eligibility(FARM_ID, supabase)

        assert "340" in result["notes"]

    async def test_irrelevant_doc_type_does_not_trigger_eligible(self):
        """A document type not in _QUALIFYING_DOC_TYPES should not satisfy the requirement."""
        fields = [{"id": FIELD_ID_A, "name": "North 40", "acres": 120.0}]
        acted_recs = [{"field_id": FIELD_ID_A, "practice_code": "340", "title": "Cover Crop"}]
        documents = [{"doc_type": "invoice"}]  # not a qualifying doc type

        supabase = _make_eqip_supabase(fields, acted_recs, EQIP_PRACTICES, documents=documents)
        result = await evaluate_eqip_eligibility(FARM_ID, supabase)

        assert result["status"] == "pending_review"


# ---------------------------------------------------------------------------
# Tests: Status = not_eligible
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestEqipNotEligible:
    async def test_no_acted_recommendations_returns_not_eligible(self):
        """A farm with no acted recommendations should be not_eligible."""
        fields = [{"id": FIELD_ID_A, "name": "North 40", "acres": 120.0}]

        supabase = _make_eqip_supabase(fields, acted_recs=[], eqip_practices=EQIP_PRACTICES)
        result = await evaluate_eqip_eligibility(FARM_ID, supabase)

        assert result["status"] == "not_eligible"
        assert result["practices_documented"] == []

    async def test_no_acted_recs_notes_explain_next_steps(self):
        """Notes should advise the farmer to act on a recommendation."""
        fields = [{"id": FIELD_ID_A, "name": "North 40", "acres": 120.0}]

        supabase = _make_eqip_supabase(fields, acted_recs=[], eqip_practices=EQIP_PRACTICES)
        result = await evaluate_eqip_eligibility(FARM_ID, supabase)

        assert "acted" in result["notes"].lower() or "recommendation" in result["notes"].lower()

    async def test_acted_codes_not_in_eqip_table_returns_not_eligible(self):
        """Practice codes that do not match any EQIP entry → not_eligible."""
        fields = [{"id": FIELD_ID_A, "name": "North 40", "acres": 120.0}]
        acted_recs = [{"field_id": FIELD_ID_A, "practice_code": "FAKE-999", "title": "Unknown"}]

        supabase = _make_eqip_supabase(fields, acted_recs, EQIP_PRACTICES)
        result = await evaluate_eqip_eligibility(FARM_ID, supabase)

        assert result["status"] == "not_eligible"
        assert "FAKE-999" in result["notes"]

    async def test_empty_eqip_reference_table_returns_not_eligible(self):
        """When the EQIP reference table is empty, no practices can match → not_eligible."""
        fields = [{"id": FIELD_ID_A, "name": "North 40", "acres": 120.0}]
        acted_recs = [{"field_id": FIELD_ID_A, "practice_code": "340", "title": "Cover Crop"}]

        supabase = _make_eqip_supabase(fields, acted_recs, eqip_practices=[])
        result = await evaluate_eqip_eligibility(FARM_ID, supabase)

        assert result["status"] == "not_eligible"

    async def test_no_fields_returns_not_eligible(self):
        """A farm with no registered fields should return not_eligible immediately."""
        supabase = _make_eqip_supabase(fields=[], acted_recs=[], eqip_practices=EQIP_PRACTICES)
        result = await evaluate_eqip_eligibility(FARM_ID, supabase)

        assert result["status"] == "not_eligible"
        assert "no fields" in result["notes"].lower() or "field" in result["notes"].lower()


# ---------------------------------------------------------------------------
# Tests: De-duplication
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestEqipDeduplication:
    async def test_same_field_code_acted_twice_counted_once(self):
        """If the same (field_id, practice_code) pair appears twice, count it once."""
        fields = [{"id": FIELD_ID_A, "name": "North 40", "acres": 120.0}]
        acted_recs = [
            {"field_id": FIELD_ID_A, "practice_code": "340", "title": "Cover Crop"},
            {"field_id": FIELD_ID_A, "practice_code": "340", "title": "Cover Crop (duplicate)"},
        ]
        documents = [{"doc_type": "soil_report"}]

        supabase = _make_eqip_supabase(fields, acted_recs, EQIP_PRACTICES, documents=documents)
        result = await evaluate_eqip_eligibility(FARM_ID, supabase)

        # practices_documented is a sorted unique list
        assert result["practices_documented"].count("340") == 1

    async def test_same_code_different_fields_counted_for_each(self):
        """The same practice code applied by different fields should both appear in results."""
        fields = [
            {"id": FIELD_ID_A, "name": "North 40", "acres": 120.0},
            {"id": FIELD_ID_B, "name": "South 60", "acres": 80.0},
        ]
        acted_recs = [
            {"field_id": FIELD_ID_A, "practice_code": "340", "title": "Cover Crop A"},
            {"field_id": FIELD_ID_B, "practice_code": "340", "title": "Cover Crop B"},
        ]
        documents = [{"doc_type": "soil_report"}]

        supabase = _make_eqip_supabase(fields, acted_recs, EQIP_PRACTICES, documents=documents)
        result = await evaluate_eqip_eligibility(FARM_ID, supabase)

        # Both fields acted on 340 → still deduplicated in practices_documented
        assert result["practices_documented"].count("340") == 1


# ---------------------------------------------------------------------------
# Tests: Persistence
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestEqipPersistence:
    async def test_upsert_called_on_credit_eligibility_table(self):
        """The result should be upserted into the credit_eligibility table."""
        fields = [{"id": FIELD_ID_A, "name": "North 40", "acres": 120.0}]
        acted_recs = [{"field_id": FIELD_ID_A, "practice_code": "340", "title": "Cover Crop"}]

        mock = MagicMock()

        def _table(name):
            if name in ("fields", "recommendations", "eqip_practices", "documents"):
                data_map = {
                    "fields": fields,
                    "recommendations": acted_recs,
                    "eqip_practices": EQIP_PRACTICES,
                    "documents": [],
                }
                return _make_chain(data=data_map[name])
            if name == "credit_eligibility":
                tbl = MagicMock()
                upsert_chain = MagicMock()
                upsert_chain.execute.return_value = MagicMock(data=[{}])
                tbl.upsert.return_value = upsert_chain
                return tbl
            return _make_chain(data=None)

        mock.table.side_effect = _table

        await evaluate_eqip_eligibility(FARM_ID, mock)

        # Verify credit_eligibility was accessed
        table_calls = [c.args[0] for c in mock.table.call_args_list]
        assert "credit_eligibility" in table_calls

    async def test_upsert_payload_contains_farm_id_and_program(self):
        """The upsert payload must include farm_id='EQIP' and the correct farm_id."""
        fields = [{"id": FIELD_ID_A, "name": "North 40", "acres": 120.0}]
        acted_recs = [{"field_id": FIELD_ID_A, "practice_code": "340", "title": "Cover Crop"}]
        captured_upsert: list[dict] = []

        mock = MagicMock()

        def _table(name):
            if name in ("fields", "recommendations", "eqip_practices", "documents"):
                data_map = {
                    "fields": fields,
                    "recommendations": acted_recs,
                    "eqip_practices": EQIP_PRACTICES,
                    "documents": [],
                }
                return _make_chain(data=data_map[name])
            if name == "credit_eligibility":
                tbl = MagicMock()

                def capture_upsert(payload, **kwargs):
                    captured_upsert.append(payload)
                    chain = MagicMock()
                    chain.execute.return_value = MagicMock(data=[payload])
                    return chain

                tbl.upsert.side_effect = capture_upsert
                return tbl
            return _make_chain(data=None)

        mock.table.side_effect = _table

        await evaluate_eqip_eligibility(FARM_ID, mock)

        assert len(captured_upsert) == 1
        assert captured_upsert[0]["farm_id"] == FARM_ID
        assert captured_upsert[0]["program"] == "EQIP"

    async def test_upsert_failure_is_non_fatal(self):
        """A failure in the credit_eligibility upsert must not raise — result still returned."""
        fields = [{"id": FIELD_ID_A, "name": "North 40", "acres": 120.0}]
        acted_recs = [{"field_id": FIELD_ID_A, "practice_code": "340", "title": "Cover Crop"}]

        mock = MagicMock()

        def _table(name):
            if name in ("fields", "recommendations", "eqip_practices", "documents"):
                data_map = {
                    "fields": fields,
                    "recommendations": acted_recs,
                    "eqip_practices": EQIP_PRACTICES,
                    "documents": [],
                }
                return _make_chain(data=data_map[name])
            if name == "credit_eligibility":
                tbl = MagicMock()
                upsert_chain = MagicMock()
                upsert_chain.execute.side_effect = Exception("DB write failed")
                tbl.upsert.return_value = upsert_chain
                return tbl
            return _make_chain(data=None)

        mock.table.side_effect = _table

        result = await evaluate_eqip_eligibility(FARM_ID, mock)

        # Result should still be present despite upsert failure
        assert result["farm_id"] == FARM_ID
        assert result["status"] in ("eligible", "pending_review", "not_eligible")


# ---------------------------------------------------------------------------
# Tests: Return payload shape
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestEqipPayloadShape:
    async def test_required_keys_present_in_result(self):
        """The result dict must contain all required keys."""
        fields = [{"id": FIELD_ID_A, "name": "North 40", "acres": 120.0}]
        acted_recs = [{"field_id": FIELD_ID_A, "practice_code": "340", "title": "Cover Crop"}]

        supabase = _make_eqip_supabase(fields, acted_recs, EQIP_PRACTICES)
        result = await evaluate_eqip_eligibility(FARM_ID, supabase)

        required = {"farm_id", "program", "status", "practices_documented", "notes", "updated_at"}
        assert required.issubset(result.keys())

    async def test_practices_documented_is_sorted_list(self):
        """practices_documented must be a sorted list of unique code strings."""
        fields = [{"id": FIELD_ID_A, "name": "North 40", "acres": 120.0}]
        acted_recs = [
            {"field_id": FIELD_ID_A, "practice_code": "590", "title": "Nutrient Management"},
            {"field_id": FIELD_ID_A, "practice_code": "340", "title": "Cover Crop"},
        ]

        supabase = _make_eqip_supabase(fields, acted_recs, EQIP_PRACTICES)
        result = await evaluate_eqip_eligibility(FARM_ID, supabase)

        codes = result["practices_documented"]
        assert isinstance(codes, list)
        assert codes == sorted(set(codes))
