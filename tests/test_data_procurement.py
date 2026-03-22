"""
Unit tests for confidential_data_procurement.
Tests cover: metrics computation, critical checks, component scores,
quality score formula, price formula, deal condition, run_deterministic,
guardrails (filter + validator), init handler, run_skill, and skill_card.
"""
from __future__ import annotations

import io
import uuid

import pandas as pd
import pytest

from skills.confidential_data_procurement.config import (
    CRITICAL_DUPLICATE_THRESHOLD,
    DEFAULT_SCORE_WEIGHTS,
)
from skills.confidential_data_procurement.deterministic import (
    check_critical,
    check_deal,
    compute_component_scores,
    compute_metrics,
    compute_price,
    compute_quality_score,
    run_deterministic,
)
from skills.confidential_data_procurement.ingest import _datasets, cleanup, procurement_upload_handler
from skills.confidential_data_procurement.models import BuyerPolicy, SupplierSubmission


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_policy(**overrides) -> BuyerPolicy:
    defaults = dict(
        required_columns=["transaction_id", "amount", "is_fraud"],
        min_rows=100,
        max_null_rate=0.05,
        max_duplicate_rate=0.10,
        min_label_rate=0.02,
        label_column="is_fraud",
        forbidden_columns=["ssn", "dob"],
        max_budget=5000.0,
        base_price=500.0,
    )
    defaults.update(overrides)
    return BuyerPolicy(**defaults)


def _make_df(rows=150, null_amount_rate=0.0, dup_rate=0.0, cols=None) -> pd.DataFrame:
    """Generate a clean fraud-like DataFrame."""
    import numpy as np
    np.random.seed(0)
    base_n = int(rows * (1 - dup_rate))
    df = pd.DataFrame({
        "transaction_id": [f"txn_{i:04d}" for i in range(base_n)],
        "amount": [round(float(i * 10.5), 2) for i in range(base_n)],
        "is_fraud": [1 if i % 25 == 0 else 0 for i in range(base_n)],
    })
    if cols:
        df = df[[c for c in cols if c in df.columns]]
    if null_amount_rate > 0:
        n_nulls = int(base_n * null_amount_rate)
        df.loc[:n_nulls, "amount"] = None
    if dup_rate > 0:
        extra = int(rows * dup_rate)
        df = pd.concat([df, df.iloc[:extra]], ignore_index=True)
    return df


def _register_df(df: pd.DataFrame, metadata: dict | None = None) -> str:
    """Store a DataFrame in the ingest store and return its dataset_id."""
    dataset_id = str(uuid.uuid4())
    _datasets[dataset_id] = {
        "df": df,
        "metadata": metadata or {},
        "column_definitions": {},
        "seller_claims": {},
        "instance_id": "test_instance",
    }
    return dataset_id


# ---------------------------------------------------------------------------
# compute_metrics
# ---------------------------------------------------------------------------

class TestComputeMetrics:
    def test_basic_counts(self):
        df = _make_df(rows=150)
        policy = _make_policy()
        m = compute_metrics(df, policy)
        assert m.row_count == 150
        assert "transaction_id" in m.column_names
        assert m.critical_failure is False
        assert m.hard_constraints_pass is True

    def test_null_rates(self):
        df = _make_df(rows=100, null_amount_rate=0.20)
        policy = _make_policy()
        m = compute_metrics(df, policy)
        assert m.null_rate_by_column["amount"] > 0.15
        assert m.overall_null_rate > 0.0

    def test_duplicate_rate(self):
        df = _make_df(rows=100, dup_rate=0.30)
        policy = _make_policy()
        m = compute_metrics(df, policy)
        assert m.duplicate_rate > 0.20

    def test_label_rate(self):
        df = _make_df(rows=100)
        policy = _make_policy(label_column="is_fraud")
        m = compute_metrics(df, policy)
        assert m.label_rate is not None
        assert 0 < m.label_rate < 0.1  # ~4% fraud

    def test_no_label_column(self):
        df = _make_df(rows=100)
        policy = _make_policy(label_column=None, min_label_rate=None)
        m = compute_metrics(df, policy)
        assert m.label_rate is None

    def test_forbidden_column_detected(self):
        df = _make_df(rows=50)
        df["ssn"] = "xxx-xx-0000"
        policy = _make_policy()
        m = compute_metrics(df, policy)
        assert "ssn" in m.forbidden_columns_present
        assert m.hard_constraints_pass is False

    def test_empty_dataframe(self):
        df = pd.DataFrame(columns=["transaction_id", "amount", "is_fraud"])
        policy = _make_policy()
        m = compute_metrics(df, policy)
        assert m.row_count == 0
        assert m.critical_failure is True
        assert m.hard_constraints_pass is False


# ---------------------------------------------------------------------------
# check_critical
# ---------------------------------------------------------------------------

class TestCheckCritical:
    def test_clean_df_not_critical(self):
        df = _make_df(rows=100)
        policy = _make_policy()
        m = compute_metrics(df, policy)
        is_crit, reason = check_critical(m)
        assert is_crit is False
        assert reason is None

    def test_forbidden_col_is_critical(self):
        df = _make_df(rows=50)
        df["ssn"] = "xxx"
        policy = _make_policy()
        m = compute_metrics(df, policy)
        is_crit, reason = check_critical(m)
        assert is_crit is True
        assert "ssn" in reason.lower()

    def test_high_duplicate_rate_is_critical(self):
        df = _make_df(rows=100, dup_rate=CRITICAL_DUPLICATE_THRESHOLD + 0.05)
        policy = _make_policy()
        m = compute_metrics(df, policy)
        is_crit, reason = check_critical(m)
        assert is_crit is True
        assert "duplicate" in reason.lower()

    def test_empty_df_is_critical(self):
        df = pd.DataFrame(columns=["a", "b"])
        policy = _make_policy()
        m = compute_metrics(df, policy)
        is_crit, reason = check_critical(m)
        assert is_crit is True


# ---------------------------------------------------------------------------
# compute_component_scores
# ---------------------------------------------------------------------------

class TestComponentScores:
    def test_perfect_dataset_scores(self):
        df = _make_df(rows=200)
        policy = _make_policy(min_rows=100)
        m = compute_metrics(df, policy)
        scores = compute_component_scores(m, policy)
        assert scores["coverage"] == 1.0
        assert scores["risk"] == 1.0
        assert scores["null"] == 1.0  # no nulls
        assert scores["duplicate"] == 1.0  # no dups

    def test_coverage_below_min(self):
        df = _make_df(rows=50)
        policy = _make_policy(min_rows=200)
        m = compute_metrics(df, policy)
        scores = compute_component_scores(m, policy)
        assert scores["coverage"] == pytest.approx(0.25, abs=0.01)

    def test_null_score_penalised(self):
        df = _make_df(rows=100, null_amount_rate=0.20)
        policy = _make_policy(max_null_rate=0.05)
        m = compute_metrics(df, policy)
        scores = compute_component_scores(m, policy)
        assert scores["null"] < 0.5

    def test_risk_score_zero_on_forbidden(self):
        df = _make_df(rows=50)
        df["ssn"] = "xxx"
        policy = _make_policy()
        m = compute_metrics(df, policy)
        scores = compute_component_scores(m, policy)
        assert scores["risk"] == 0.0

    def test_schema_score_placeholder(self):
        df = _make_df(rows=100)
        policy = _make_policy()
        m = compute_metrics(df, policy)
        scores = compute_component_scores(m, policy)
        assert scores["schema"] == 0.5  # placeholder until agent

    def test_claim_veracity_placeholder(self):
        df = _make_df(rows=100)
        policy = _make_policy()
        m = compute_metrics(df, policy)
        scores = compute_component_scores(m, policy)
        assert scores["claim_veracity"] == 1.0  # placeholder until agent


# ---------------------------------------------------------------------------
# compute_quality_score
# ---------------------------------------------------------------------------

class TestQualityScore:
    def test_default_weights_sum_to_one(self):
        assert abs(sum(DEFAULT_SCORE_WEIGHTS.values()) - 1.0) < 0.001

    def test_perfect_scores_give_one(self):
        perfect = {k: 1.0 for k in DEFAULT_SCORE_WEIGHTS}
        assert compute_quality_score(perfect, _make_policy()) == pytest.approx(1.0)

    def test_zero_scores_give_zero(self):
        zeros = {k: 0.0 for k in DEFAULT_SCORE_WEIGHTS}
        assert compute_quality_score(zeros, _make_policy()) == pytest.approx(0.0)

    def test_clamped_to_zero_one(self):
        over = {k: 2.0 for k in DEFAULT_SCORE_WEIGHTS}
        assert compute_quality_score(over, _make_policy()) == 1.0

    def test_custom_weights_respected(self):
        policy = _make_policy(score_weights={k: 1/7 for k in DEFAULT_SCORE_WEIGHTS})
        scores = {k: 1.0 for k in DEFAULT_SCORE_WEIGHTS}
        assert compute_quality_score(scores, policy) == pytest.approx(1.0, abs=0.01)


# ---------------------------------------------------------------------------
# compute_price
# ---------------------------------------------------------------------------

class TestComputePrice:
    def test_s_zero_gives_base_price(self):
        assert compute_price(0.0, 500.0, 5000.0) == 500.0

    def test_s_one_gives_max_budget(self):
        assert compute_price(1.0, 500.0, 5000.0) == 5000.0

    def test_midpoint(self):
        assert compute_price(0.5, 0.0, 1000.0) == 500.0

    def test_rounded_to_two_decimals(self):
        result = compute_price(0.333, 0.0, 1000.0)
        assert result == round(result, 2)

    def test_formula_correct(self):
        S, base, budget = 0.87, 500.0, 5000.0
        expected = round(500.0 + (5000.0 - 500.0) * 0.87, 2)
        assert compute_price(S, base, budget) == expected


# ---------------------------------------------------------------------------
# check_deal
# ---------------------------------------------------------------------------

class TestCheckDeal:
    def test_deal_passes(self):
        assert check_deal(True, 3000.0, 4000.0, 5000.0) is True

    def test_reserve_above_payment(self):
        assert check_deal(True, 4500.0, 4000.0, 5000.0) is False

    def test_payment_above_budget(self):
        # P > B can't normally happen (P = B * S ≤ B), but guard anyway
        assert check_deal(True, 100.0, 6000.0, 5000.0) is False

    def test_hard_constraints_fail(self):
        assert check_deal(False, 3000.0, 4000.0, 5000.0) is False

    def test_exact_reserve_equals_payment(self):
        assert check_deal(True, 4000.0, 4000.0, 5000.0) is True  # R == P: ok


# ---------------------------------------------------------------------------
# run_deterministic (integration)
# ---------------------------------------------------------------------------

class TestRunDeterministic:
    def test_good_dataset_deal_passes(self):
        df = _make_df(rows=200)
        policy = _make_policy(min_rows=100, max_budget=5000.0, base_price=500.0)
        dataset_id = _register_df(df)
        try:
            result = run_deterministic(dataset_id, policy, reserve_price=1000.0)
            assert result["deal"] is True
            assert result["quality_score"] > 0.5
            assert result["proposed_payment"] >= 500.0
            assert result["proposed_payment"] <= 5000.0
            assert not result["metrics"].critical_failure
        finally:
            cleanup(dataset_id)

    def test_critical_failure_early_exit(self):
        df = _make_df(rows=50)
        df["ssn"] = "xxx"
        policy = _make_policy()
        dataset_id = _register_df(df)
        try:
            result = run_deterministic(dataset_id, policy, reserve_price=100.0)
            assert result["metrics"].critical_failure is True
            assert result["deal"] is False
            assert result["quality_score"] == 0.0
            assert result["proposed_payment"] == policy.base_price
            assert len(result["notes"]) > 0
        finally:
            cleanup(dataset_id)

    def test_high_null_reduces_price(self):
        df_clean = _make_df(rows=150)
        df_nulls = _make_df(rows=150, null_amount_rate=0.30)
        policy = _make_policy(max_null_rate=0.05, max_budget=5000.0, base_price=0.0)

        id_clean = _register_df(df_clean)
        id_nulls = _register_df(df_nulls)
        try:
            clean_result = run_deterministic(id_clean, policy, reserve_price=0.0)
            nulls_result = run_deterministic(id_nulls, policy, reserve_price=0.0)
            assert nulls_result["proposed_payment"] < clean_result["proposed_payment"]
        finally:
            cleanup(id_clean)
            cleanup(id_nulls)

    def test_reserve_above_payment_no_deal(self):
        df = _make_df(rows=150)
        policy = _make_policy(min_rows=100, max_budget=1000.0, base_price=0.0)
        dataset_id = _register_df(df)
        try:
            result = run_deterministic(dataset_id, policy, reserve_price=9999.0)
            assert result["deal"] is False
            assert any("reserve" in n.lower() for n in result["notes"])
        finally:
            cleanup(dataset_id)

    def test_notes_populated_on_partial_failure(self):
        df = _make_df(rows=50)  # below min_rows=100
        policy = _make_policy(min_rows=100)
        dataset_id = _register_df(df)
        try:
            result = run_deterministic(dataset_id, policy, reserve_price=0.0)
            assert any("row count" in n.lower() for n in result["notes"])
        finally:
            cleanup(dataset_id)

    def test_dataset_not_found_raises(self):
        policy = _make_policy()
        with pytest.raises(KeyError):
            run_deterministic("nonexistent_id", policy, reserve_price=100.0)


# ---------------------------------------------------------------------------
# ProcurementFilter
# ---------------------------------------------------------------------------

from skills.confidential_data_procurement.guardrails import (
    ProcurementFilter,
    validate_tool_output,
)


class TestProcurementFilter:
    def _result(self) -> dict:
        return {
            "submission_id": "sub-1",
            "deal": True,
            "quality_score": 0.85,
            "proposed_payment": 3000.0,
            "hard_constraints_pass": True,
            "settlement_status": "authorized",
            "release_token": "tok-abc",
            "notes": [],
            "explanation": "Looks good.",
            "claim_verification": None,
            "schema_matching": None,
            "buyer_response": "accept",
            "supplier_response": "accept",
            "renegotiation_used": False,
        }

    def test_buyer_sees_quality_score(self):
        f = ProcurementFilter(role="admin")
        out = f.filter_keys(self._result())
        assert "quality_score" in out

    def test_supplier_hides_quality_score(self):
        f = ProcurementFilter(role="user")
        out = f.filter_keys(self._result())
        assert "quality_score" not in out
        assert "hard_constraints_pass" not in out

    def test_supplier_still_sees_payment(self):
        f = ProcurementFilter(role="user")
        out = f.filter_keys(self._result())
        assert "proposed_payment" in out
        assert "deal" in out

    def test_check_bounds_clamps_high(self):
        f = ProcurementFilter(role="admin")
        r = {"quality_score": 1.5}
        assert f.check_bounds(r)["quality_score"] == 1.0

    def test_check_bounds_clamps_low(self):
        f = ProcurementFilter(role="admin")
        r = {"quality_score": -0.3}
        assert f.check_bounds(r)["quality_score"] == 0.0

    def test_check_bounds_passes_valid(self):
        f = ProcurementFilter(role="admin")
        r = {"quality_score": 0.72}
        assert f.check_bounds(r)["quality_score"] == pytest.approx(0.72)

    def test_unknown_keys_stripped(self):
        f = ProcurementFilter(role="admin")
        r = self._result()
        r["_internal_secret"] = "max_budget=9000"
        out = f.filter_keys(r)
        assert "_internal_secret" not in out

    def test_leakage_flagged_in_apply(self):
        f = ProcurementFilter(role="admin")
        result = self._result()
        # Inject a long substring into explanation that also appears in raw_inputs
        leaked = "SENSITIVE_CELL_VALUE_XYZ_1234567890"
        result["explanation"] = f"The data shows {leaked} is common."
        filtered = f.apply([result], [leaked])
        assert "_leakage_warning" in filtered[0]


# ---------------------------------------------------------------------------
# validate_tool_output
# ---------------------------------------------------------------------------

class TestValidateToolOutput:
    def test_clean_stats_pass(self):
        output = "count: 150\nmean: 4.2\nstd: 1.1\nmin: 0.0\nmax: 10.0"
        assert validate_tool_output(output) == output

    def test_oversized_raises(self):
        big = "x" * 5000
        with pytest.raises(ValueError, match="too large"):
            validate_tool_output(big)

    def test_raw_rows_raises(self):
        # 6 CSV-like lines — over the threshold of 5
        rows = "\n".join(f"txn_{i},100.{i},0" for i in range(6))
        with pytest.raises(ValueError, match="CSV-like"):
            validate_tool_output(rows)

    def test_exactly_at_raw_row_limit_passes(self):
        # exactly MAX_RAW_ROW_LINES (5) CSV-like lines — should pass
        rows = "\n".join(f"txn_{i},100.{i},0" for i in range(5))
        assert validate_tool_output(rows) == rows

    def test_high_cardinality_raises(self):
        # 51 bullet items — over the threshold of 50
        items = "\n".join(f"- value_{i}: {i}" for i in range(51))
        with pytest.raises(ValueError, match="enumerates"):
            validate_tool_output(items)

    def test_exactly_at_cardinality_limit_passes(self):
        items = "\n".join(f"- value_{i}: {i}" for i in range(50))
        assert validate_tool_output(items) == items

    def test_empty_string_passes(self):
        assert validate_tool_output("") == ""


# ---------------------------------------------------------------------------
# procurement_init_handler
# ---------------------------------------------------------------------------

from unittest.mock import patch

from skills.confidential_data_procurement.init import (
    _parse_llm_response,
    procurement_init_handler,
)


class _FakeLLM:
    """Minimal LLM stub — returns a fixed content string."""
    def __init__(self, content: str):
        self._content = content

    def invoke(self, _messages):
        class _R:
            pass
        r = _R()
        r.content = self._content
        return r


_SEEDED_CONV = [
    {"role": "system", "content": "sys"},
    {"role": "ai",     "content": "greeting"},
]

_VALID_JSON = (
    '{"ready": true, "required_columns": ["txn_id", "amount", "label"], '
    '"min_rows": 500, "max_null_rate": 0.05, "max_duplicate_rate": 0.10, '
    '"max_budget": 4000.0, "base_price": 200.0, '
    '"min_label_rate": 0.02, "label_column": "label", '
    '"forbidden_columns": ["ssn"], "description": "fraud dataset"}'
)


class TestParseLlmResponse:
    def test_valid_ready_json(self):
        result = _parse_llm_response(_VALID_JSON)
        assert result is not None
        assert result["ready"] is True
        assert result["required_columns"] == ["txn_id", "amount", "label"]

    def test_markdown_fences_stripped(self):
        wrapped = f"```json\n{_VALID_JSON}\n```"
        assert _parse_llm_response(wrapped) is not None

    def test_non_json_returns_none(self):
        assert _parse_llm_response("Sure, what columns do you need?") is None

    def test_ready_false_returns_none(self):
        assert _parse_llm_response('{"ready": false, "message": "tell me more"}') is None

    def test_missing_ready_returns_none(self):
        assert _parse_llm_response('{"required_columns": ["a"]}') is None


class TestProcurementInitHandler:
    def test_first_turn_returns_greeting(self):
        result = procurement_init_handler("", [])
        assert result["status"] == "configuring"
        assert "required columns" in result["message"].lower()
        assert result["conversation"][0]["role"] == "system"

    def test_first_turn_no_llm_call(self):
        # No patch needed — should not call get_llm at all on turn 1
        result = procurement_init_handler("anything", [])
        assert result["status"] == "configuring"

    def test_valid_json_returns_ready(self):
        with patch("skills.confidential_data_procurement.init.get_llm",
                   return_value=_FakeLLM(_VALID_JSON)):
            result = procurement_init_handler("here is my policy", _SEEDED_CONV)
        assert result["status"] == "ready"
        assert result["threshold"] == 1
        policy = result["config"]
        assert policy.min_rows == 500
        assert policy.max_budget == 4000.0
        assert policy.base_price == 200.0
        assert "ssn" in policy.forbidden_columns

    def test_empty_columns_stays_configuring(self):
        bad = _VALID_JSON.replace('"txn_id", "amount", "label"', "")
        bad = bad.replace('"required_columns": [],', '"required_columns": [],')
        payload = '{"ready": true, "required_columns": [], "min_rows": 500, "max_null_rate": 0.05, "max_duplicate_rate": 0.10, "max_budget": 4000.0}'
        with patch("skills.confidential_data_procurement.init.get_llm",
                   return_value=_FakeLLM(payload)):
            result = procurement_init_handler("no columns", _SEEDED_CONV)
        assert result["status"] == "configuring"
        assert "column" in result["message"].lower()

    def test_zero_min_rows_stays_configuring(self):
        payload = '{"ready": true, "required_columns": ["a"], "min_rows": 0, "max_null_rate": 0.05, "max_duplicate_rate": 0.10, "max_budget": 1000.0}'
        with patch("skills.confidential_data_procurement.init.get_llm",
                   return_value=_FakeLLM(payload)):
            result = procurement_init_handler("zero rows", _SEEDED_CONV)
        assert result["status"] == "configuring"
        assert "rows" in result["message"].lower()

    def test_base_price_above_budget_stays_configuring(self):
        payload = '{"ready": true, "required_columns": ["a"], "min_rows": 100, "max_null_rate": 0.05, "max_duplicate_rate": 0.10, "max_budget": 500.0, "base_price": 600.0}'
        with patch("skills.confidential_data_procurement.init.get_llm",
                   return_value=_FakeLLM(payload)):
            result = procurement_init_handler("bad price", _SEEDED_CONV)
        assert result["status"] == "configuring"
        assert "base price" in result["message"].lower()

    def test_non_json_response_stays_configuring(self):
        with patch("skills.confidential_data_procurement.init.get_llm",
                   return_value=_FakeLLM("What forbidden columns do you need?")):
            result = procurement_init_handler("not ready yet", _SEEDED_CONV)
        assert result["status"] == "configuring"
        assert result["message"] == "What forbidden columns do you need?"

    def test_conversation_accumulates(self):
        with patch("skills.confidential_data_procurement.init.get_llm",
                   return_value=_FakeLLM(_VALID_JSON)):
            result = procurement_init_handler("my policy", _SEEDED_CONV)
        # seeded (2) + human (1) + ai (1) = 4
        assert len(result["conversation"]) == 4


# ---------------------------------------------------------------------------
# run_skill + skill_card
# ---------------------------------------------------------------------------

from skills.confidential_data_procurement import run_skill, skill_card


class TestRunSkill:
    def test_good_dataset_returns_deal(self):
        df = _make_df(rows=200)
        policy = _make_policy(min_rows=100, max_budget=5000.0, base_price=500.0)
        dataset_id = _register_df(df)
        try:
            sub = SupplierSubmission(
                submission_id="sub-good",
                dataset_id=dataset_id,
                dataset_name="fraud_data.csv",
                reserve_price=1000.0,
            )
            resp = run_skill([sub], policy)
            assert resp.skill == "confidential_data_procurement"
            assert len(resp.results) == 1
            r = resp.results[0]
            assert r["deal"] is True
            assert r["settlement_status"] == "pending_approval"
            assert r["proposed_payment"] >= 500.0
            assert r["quality_score"] > 0.5
        finally:
            cleanup(dataset_id)

    def test_critical_failure_returns_rejected(self):
        df = _make_df(rows=50)
        df["ssn"] = "xxx"
        policy = _make_policy()
        dataset_id = _register_df(df)
        try:
            sub = SupplierSubmission(
                submission_id="sub-bad",
                dataset_id=dataset_id,
                dataset_name="bad_data.csv",
                reserve_price=100.0,
            )
            resp = run_skill([sub], policy)
            r = resp.results[0]
            assert r["deal"] is False
            assert r["settlement_status"] == "rejected"
            assert r["quality_score"] == 0.0
        finally:
            cleanup(dataset_id)

    def test_reserve_above_payment_no_deal(self):
        df = _make_df(rows=150)
        policy = _make_policy(min_rows=100, max_budget=1000.0, base_price=0.0)
        dataset_id = _register_df(df)
        try:
            sub = SupplierSubmission(
                submission_id="sub-expensive",
                dataset_id=dataset_id,
                dataset_name="data.csv",
                reserve_price=9999.0,
            )
            resp = run_skill([sub], policy)
            r = resp.results[0]
            assert r["deal"] is False
            assert r["settlement_status"] == "rejected"
        finally:
            cleanup(dataset_id)

    def test_internal_fields_stripped_by_guardrails(self):
        """revised_budget and revised_reserve should not appear in output."""
        df = _make_df(rows=200)
        policy = _make_policy(min_rows=100, max_budget=5000.0, base_price=500.0)
        dataset_id = _register_df(df)
        try:
            sub = SupplierSubmission(
                submission_id="sub-internal",
                dataset_id=dataset_id,
                dataset_name="data.csv",
                reserve_price=100.0,
            )
            resp = run_skill([sub], policy)
            r = resp.results[0]
            assert "revised_budget" not in r
            assert "revised_reserve" not in r
        finally:
            cleanup(dataset_id)


class TestSkillCard:
    def test_card_name(self):
        assert skill_card.name == "confidential_data_procurement"

    def test_card_has_required_fields(self):
        assert skill_card.run is run_skill
        assert skill_card.input_model is SupplierSubmission
        assert skill_card.init_handler is procurement_init_handler
        assert skill_card.upload_handler is procurement_upload_handler

    def test_output_keys_superset_of_user_keys(self):
        assert skill_card.user_output_keys.issubset(skill_card.output_keys)

    def test_quality_score_buyer_only(self):
        assert "quality_score" in skill_card.output_keys
        assert "quality_score" not in skill_card.user_output_keys

    def test_metadata_serializable(self):
        meta = skill_card.metadata()
        assert meta["name"] == "confidential_data_procurement"
        assert "quality_score" in meta["output_keys"]
        assert "quality_score" not in meta["user_output_keys"]

    def test_threshold_is_one(self):
        assert skill_card.config["min_submissions"] == 1

    def test_respond_handler_registered(self):
        from skills.confidential_data_procurement import procurement_respond_handler
        assert skill_card.respond_handler is procurement_respond_handler


# ---------------------------------------------------------------------------
# Agent layer
# ---------------------------------------------------------------------------

from skills.confidential_data_procurement.agent import _parse_agent_output, _safe_defaults
from skills.confidential_data_procurement.tools import (
    get_column_stats,
    get_schema_summary,
    get_value_distribution,
    set_context,
)


_AGENT_JSON = (
    '{"schema_score": 0.8, "claim_veracity_score": 0.9, '
    '"schema_matching": {"transaction_id": "txn_id", "amount": "amount"}, '
    '"claim_verification": {"no_nulls": "disputed"}, '
    '"explanation": "Dataset looks reasonable."}'
)


class TestParseAgentOutput:
    def test_valid_json_extracted(self):
        policy = _make_policy()
        result = _parse_agent_output(_AGENT_JSON, policy, {"no_nulls": "true"})
        assert result["schema_score"] == pytest.approx(0.8)
        assert result["claim_veracity_score"] == pytest.approx(0.9)
        assert result["schema_matching"]["transaction_id"] == "txn_id"
        assert result["explanation"] == "Dataset looks reasonable."

    def test_clamped_scores(self):
        policy = _make_policy()
        bad = '{"schema_score": 2.5, "claim_veracity_score": -0.1, "explanation": "x"}'
        result = _parse_agent_output(bad, policy, {})
        assert result["schema_score"] == 1.0
        assert result["claim_veracity_score"] == 0.0

    def test_markdown_fences_stripped(self):
        policy = _make_policy()
        wrapped = f"```json\n{_AGENT_JSON}\n```"
        result = _parse_agent_output(wrapped, policy, {})
        assert result["schema_score"] == pytest.approx(0.8)

    def test_unparseable_returns_defaults(self):
        policy = _make_policy()
        result = _parse_agent_output("Sorry, I could not evaluate.", policy, {"claim": "x"})
        assert result["schema_score"] == 0.5
        assert result["claim_veracity_score"] == 1.0

    def test_safe_defaults_structure(self):
        policy = _make_policy()
        result = _safe_defaults(policy, {"low_nulls": "true"})
        assert "schema_matching" in result
        assert "claim_verification" in result
        assert result["claim_verification"]["low_nulls"] == "unverifiable"


class TestTools:
    def setup_method(self):
        self.df = _make_df(rows=50)
        self.dataset_id = _register_df(self.df)
        set_context(self.dataset_id, {
            "required_columns": ["transaction_id", "amount"],
            "column_definitions": {},
            "seller_claims": {},
        })

    def teardown_method(self):
        from skills.confidential_data_procurement.ingest import cleanup
        cleanup(self.dataset_id)

    def test_schema_summary_passes_validator(self):
        result = get_schema_summary.invoke({})
        assert "transaction_id" in result
        assert "rows:" in result

    def test_column_stats_numeric(self):
        result = get_column_stats.invoke({"column_name": "amount"})
        assert "numeric" in result
        assert "mean" in result

    def test_column_stats_missing_column(self):
        result = get_column_stats.invoke({"column_name": "nonexistent"})
        assert "not found" in result.lower()

    def test_value_distribution(self):
        result = get_value_distribution.invoke({"column_name": "is_fraud", "top_n": 5})
        assert "is_fraud" in result
        assert "distinct" in result

    def test_value_distribution_capped_at_20(self):
        result = get_value_distribution.invoke({"column_name": "amount", "top_n": 999})
        assert "top-20" in result


# ---------------------------------------------------------------------------
# respond_handler + renegotiation (3×3 matrix)
# ---------------------------------------------------------------------------

from skills.confidential_data_procurement import procurement_respond_handler


def _base_result(deal=True) -> dict:
    return {
        "submission_id": "sub-1",
        "deal": deal,
        "quality_score": 0.75,
        "proposed_payment": 3000.0,
        "hard_constraints_pass": True,
        "settlement_status": "pending_approval" if deal else "rejected",
        "release_token": None,
        "notes": [],
        "explanation": None,
        "claim_verification": None,
        "schema_matching": None,
        "buyer_response": None,
        "supplier_response": None,
        "renegotiation_used": False,
        "revised_budget": None,
        "revised_reserve": None,
    }


class TestRespondHandler:
    # --- First response only → awaiting_counterparty ---

    def test_first_buyer_response_awaits_counterparty(self):
        r = procurement_respond_handler(_base_result(), "accept", None, "buyer", _make_policy())
        assert r["settlement_status"] == "awaiting_counterparty"
        assert r["buyer_response"] == "accept"
        assert r["supplier_response"] is None

    def test_first_supplier_response_awaits_counterparty(self):
        r = procurement_respond_handler(_base_result(), "accept", None, "supplier", _make_policy())
        assert r["settlement_status"] == "awaiting_counterparty"
        assert r["supplier_response"] == "accept"

    # --- Both accept → authorized ---

    def test_both_accept_authorized(self):
        result = _base_result()
        result["buyer_response"] = "accept"
        r = procurement_respond_handler(result, "accept", None, "supplier", _make_policy())
        assert r["settlement_status"] == "authorized"
        assert r["deal"] is True
        assert r["release_token"] is not None

    # --- Any reject → rejected ---

    def test_buyer_reject_rejected(self):
        result = _base_result()
        result["supplier_response"] = "accept"
        r = procurement_respond_handler(result, "reject", None, "buyer", _make_policy())
        assert r["settlement_status"] == "rejected"
        assert r["deal"] is False

    def test_supplier_reject_rejected(self):
        result = _base_result()
        result["buyer_response"] = "accept"
        r = procurement_respond_handler(result, "reject", None, "supplier", _make_policy())
        assert r["settlement_status"] == "rejected"

    def test_both_reject_rejected(self):
        result = _base_result()
        result["buyer_response"] = "reject"
        r = procurement_respond_handler(result, "reject", None, "supplier", _make_policy())
        assert r["settlement_status"] == "rejected"

    def test_renegotiate_then_reject_rejected(self):
        result = _base_result()
        result["buyer_response"] = "renegotiate"
        result["revised_budget"] = 2500.0
        result["renegotiation_used"] = False
        r = procurement_respond_handler(result, "reject", None, "supplier", _make_policy())
        assert r["settlement_status"] == "rejected"

    # --- accept + renegotiate → authorized at proposed_payment ---

    def test_buyer_accept_supplier_renegotiate_authorized(self):
        result = _base_result()
        result["buyer_response"] = "accept"
        r = procurement_respond_handler(result, "renegotiate", 3500.0, "supplier", _make_policy())
        assert r["settlement_status"] == "authorized"
        assert r["renegotiation_used"] is True
        assert r["release_token"] is not None

    def test_supplier_accept_buyer_renegotiate_authorized(self):
        result = _base_result()
        result["supplier_response"] = "accept"
        r = procurement_respond_handler(result, "renegotiate", 2500.0, "buyer", _make_policy())
        assert r["settlement_status"] == "authorized"
        assert r["renegotiation_used"] is True

    # --- Both renegotiate ---

    def test_both_renegotiate_deal_succeeds(self):
        result = _base_result()
        result["buyer_response"] = "renegotiate"
        result["revised_budget"] = 3000.0
        r = procurement_respond_handler(result, "renegotiate", 2500.0, "supplier", _make_policy())
        assert r["settlement_status"] == "authorized"
        assert r["proposed_payment"] == 3000.0
        assert r["renegotiation_used"] is True

    def test_both_renegotiate_deal_fails(self):
        result = _base_result()
        result["buyer_response"] = "renegotiate"
        result["revised_budget"] = 1000.0
        r = procurement_respond_handler(result, "renegotiate", 2000.0, "supplier", _make_policy())
        assert r["settlement_status"] == "rejected"
        assert r["deal"] is False
        assert any("renegotiation failed" in n.lower() for n in r["notes"])

    # --- Validation errors ---

    def test_second_renegotiation_raises(self):
        result = _base_result()
        result["renegotiation_used"] = True
        result["buyer_response"] = "renegotiate"
        with pytest.raises(ValueError, match="already used"):
            procurement_respond_handler(result, "renegotiate", 2000.0, "supplier", _make_policy())

    def test_renegotiate_without_value_raises(self):
        with pytest.raises(ValueError, match="revised_value is required"):
            procurement_respond_handler(_base_result(), "renegotiate", None, "buyer", _make_policy())

    def test_buyer_revised_above_budget_raises(self):
        with pytest.raises(ValueError, match="max budget"):
            procurement_respond_handler(
                _base_result(), "renegotiate", 99999.0, "buyer", _make_policy()
            )

    def test_supplier_negative_reserve_raises(self):
        with pytest.raises(ValueError, match="negative"):
            procurement_respond_handler(
                _base_result(), "renegotiate", -100.0, "supplier", _make_policy()
            )
