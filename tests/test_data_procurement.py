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
