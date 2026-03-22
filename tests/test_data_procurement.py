"""
Unit tests for confidential_data_procurement — deterministic layer.
Tests cover: metrics computation, critical checks, component scores,
quality score formula, price formula, deal condition, and run_deterministic.
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
from skills.confidential_data_procurement.ingest import _datasets, cleanup
from skills.confidential_data_procurement.models import BuyerPolicy


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
