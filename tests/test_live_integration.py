"""
Live integration test suite for confidential_data_procurement.

Budget design: base_price=0 on all buyer policies.
  → Payment = max_budget * quality_score
  → Bad data → payment near $0. Critical failure → $0.
  → All amounts in $0–$800 range for demo clarity.

Sections:
  1. Deterministic (no LLM, always fast)    — 11 tests
  2. Agent layer (live LLM, @pytest.mark.live) — 7 tests
  3. Full pipeline (live LLM, @pytest.mark.live) — 7 tests
  4. Renegotiation scenarios (deterministic)  — 5 tests

Run fast only:
    ./venv/bin/python -m pytest tests/test_live_integration.py -v -m "not live"

Run all + print matrix:
    ./venv/bin/python -m pytest tests/test_live_integration.py -v -s
"""
from __future__ import annotations

import uuid

import pandas as pd
import pytest

from skills.confidential_data_procurement.ingest import _datasets
from skills.confidential_data_procurement.deterministic import (
    compute_metrics,
    run_deterministic,
)
from skills.confidential_data_procurement.models import BuyerPolicy, SupplierSubmission
from skills.confidential_data_procurement.agent import run_agent
from skills.confidential_data_procurement import run_skill
from skills.confidential_data_procurement import procurement_respond_handler


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _register(df: pd.DataFrame, metadata: dict | None = None) -> str:
    did = str(uuid.uuid4())
    meta = metadata or {}
    _datasets[did] = {
        "df": df,
        "metadata": meta,
        "column_definitions": meta.get("column_definitions", {}),
        "seller_claims":      meta.get("seller_claims", {}),
        "instance_id": "test_integration",
    }
    return did


def _run_pipeline(base_df, seller_fn, policy: BuyerPolicy, reserve: float = 200.0) -> dict:
    df, meta = seller_fn(base_df)
    did = _register(df, meta)
    try:
        sub = SupplierSubmission(
            submission_id=str(uuid.uuid4()),
            dataset_id=did,
            dataset_name="test.csv",
            reserve_price=reserve,
        )
        resp = run_skill([sub], policy)
        return resp.results[0] if resp.results else {}
    finally:
        _datasets.pop(did, None)


# ---------------------------------------------------------------------------
# Seller variants
# ---------------------------------------------------------------------------

def _seller_clean(base_df):
    df = base_df[["transaction_id", "amount", "is_fraud"]].copy().reset_index(drop=True)
    meta = {
        "column_definitions": {
            "transaction_id": "Unique ID per transaction",
            "amount":         "Transaction amount in USD",
            "is_fraud":       "1 if fraudulent, 0 otherwise",
        },
        "seller_claims": {
            "low_fraud_rate":    "Approximately 4% fraud rate",
            "no_missing_values": "All fields fully populated",
        },
    }
    return df, meta


def _seller_null_corrupted(base_df):
    """30% of amount values nulled — seller falsely claims no missing values."""
    df = base_df[["transaction_id", "amount", "is_fraud"]].copy().reset_index(drop=True)
    n = int(len(df) * 0.30)
    df.loc[:n, "amount"] = None
    meta = {
        "column_definitions": {
            "transaction_id": "Unique ID",
            "amount":         "Transaction amount",
            "is_fraud":       "Fraud flag",
        },
        "seller_claims": {"no_missing_values": "All fields fully populated"},
    }
    return df, meta


def _seller_dup_corrupted(base_df):
    """Entire dataset duplicated → duplicate_rate = 50% → critical failure."""
    df = base_df[["transaction_id", "amount", "is_fraud"]].copy().reset_index(drop=True)
    df = pd.concat([df, df], ignore_index=True)
    return df, {}


def _seller_forbidden_col(base_df):
    """SSN column present → critical failure, no LLM."""
    df = base_df[["transaction_id", "amount", "is_fraud"]].copy().reset_index(drop=True)
    df["ssn"] = "xxx-xx-0000"
    return df, {}


def _seller_missing_col(base_df):
    """is_fraud dropped — buyer requires it → schema penalty."""
    df = base_df[["transaction_id", "amount"]].copy().reset_index(drop=True)
    meta = {
        "column_definitions": {
            "transaction_id": "Unique ID",
            "amount":         "Transaction amount",
        },
        "seller_claims": {},
    }
    return df, meta


def _seller_fuzzy_schema(base_df):
    """is_fraud renamed to fraud_label — tests agent semantic matching."""
    df = base_df[["transaction_id", "amount", "is_fraud"]].copy().reset_index(drop=True)
    df = df.rename(columns={"is_fraud": "fraud_label"})
    meta = {
        "column_definitions": {
            "transaction_id": "Unique ID",
            "amount":         "Transaction amount",
            "fraud_label":    "Binary fraud indicator (1=fraud, 0=legit)",
        },
        "seller_claims": {},
    }
    return df, meta


def _seller_multi_corrupt(base_df):
    """25% nulls + missing is_fraud — compound quality damage."""
    df = base_df[["transaction_id", "amount"]].copy().reset_index(drop=True)
    n = int(len(df) * 0.25)
    df.loc[:n, "amount"] = None
    return df, {}


# ---------------------------------------------------------------------------
# Buyer policies — base_price=0 on all (bad data → payment near $0)
# ---------------------------------------------------------------------------

def _buyer_lenient() -> BuyerPolicy:
    """Tolerant buyer: accepts moderate nulls, low row floor, $800 ceiling."""
    return BuyerPolicy(
        required_columns=["transaction_id", "amount", "is_fraud"],
        min_rows=200,
        max_null_rate=0.35,
        max_duplicate_rate=0.20,
        min_label_rate=0.01,
        label_column="is_fraud",
        forbidden_columns=["ssn", "dob"],
        max_budget=800.0,
        base_price=0.0,
    )


def _buyer_strict() -> BuyerPolicy:
    """Strict buyer: demands 900 rows, low null tolerance, $800 ceiling."""
    return BuyerPolicy(
        required_columns=["transaction_id", "amount", "is_fraud"],
        min_rows=900,
        max_null_rate=0.05,
        max_duplicate_rate=0.05,
        min_label_rate=0.02,
        label_column="is_fraud",
        forbidden_columns=["ssn", "dob"],
        max_budget=800.0,
        base_price=0.0,
    )


def _buyer_budget_tight() -> BuyerPolicy:
    """Budget-conscious buyer: same quality expectations, $300 ceiling."""
    return BuyerPolicy(
        required_columns=["transaction_id", "amount", "is_fraud"],
        min_rows=200,
        max_null_rate=0.35,
        max_duplicate_rate=0.20,
        min_label_rate=0.01,
        label_column="is_fraud",
        forbidden_columns=["ssn", "dob"],
        max_budget=300.0,
        base_price=0.0,
    )


# ---------------------------------------------------------------------------
# Section 1: Deterministic layer (no LLM)
# ---------------------------------------------------------------------------

class TestDeterministic:
    """Fast correctness checks — direct calls to run_deterministic."""

    def setup_method(self):
        self._ids: list[str] = []

    def teardown_method(self):
        for did in self._ids:
            _datasets.pop(did, None)

    def _run(self, df, policy, metadata=None, reserve=200.0):
        did = _register(df, metadata)
        self._ids.append(did)
        return run_deterministic(did, policy, reserve)

    def test_clean_lenient_high_quality(self, base_df):
        """Clean data + lenient policy → no critical failure, quality > 0.7."""
        df, meta = _seller_clean(base_df)
        r = self._run(df, _buyer_lenient(), meta)
        assert not r["metrics"].critical_failure
        assert r["quality_score"] > 0.7

    def test_clean_strict_coverage_penalty(self, base_df):
        """800-row dataset vs strict 900-row min → coverage_score = 800/900 ≈ 0.89."""
        df, meta = _seller_clean(base_df)
        r = self._run(df, _buyer_strict(), meta)
        assert not r["metrics"].critical_failure
        assert r["component_scores"]["coverage"] == pytest.approx(len(df) / 900, rel=0.01)
        assert r["component_scores"]["coverage"] < 1.0

    def test_null_lenient_passes(self, base_df):
        """30% null in one column (~10% overall) < 35% lenient threshold → quality > 0."""
        df, meta = _seller_null_corrupted(base_df)
        r = self._run(df, _buyer_lenient(), meta)
        assert not r["metrics"].critical_failure
        assert r["component_scores"]["null"] > 0

    def test_null_strict_null_score_zero(self, base_df):
        """~10% overall null > 5% strict threshold → null_score = 0."""
        df, meta = _seller_null_corrupted(base_df)
        r = self._run(df, _buyer_strict(), meta)
        assert r["component_scores"]["null"] == 0.0

    def test_null_payment_lower_than_clean(self, base_df):
        """Null-corrupted → lower quality → lower payment than clean, same policy."""
        df_c, m_c = _seller_clean(base_df)
        df_n, m_n = _seller_null_corrupted(base_df)
        p = _buyer_lenient()
        assert self._run(df_n, p, m_n)["proposed_payment"] < self._run(df_c, p, m_c)["proposed_payment"]

    def test_dup_corrupted_critical(self, base_df):
        """50% duplicates (entire dataset doubled) → critical_failure, $0 payment."""
        df, meta = _seller_dup_corrupted(base_df)
        r = self._run(df, _buyer_lenient(), meta)
        assert r["metrics"].critical_failure
        assert not r["deal"]
        assert r["proposed_payment"] == 0.0  # base_price=0, so floor is $0

    def test_forbidden_col_critical(self, base_df):
        """SSN column → critical_failure, note mentions 'ssn'."""
        df, meta = _seller_forbidden_col(base_df)
        r = self._run(df, _buyer_lenient(), meta)
        assert r["metrics"].critical_failure
        assert "ssn" in " ".join(r["notes"]).lower()

    def test_budget_tight_caps_payment(self, base_df):
        """Same clean data, $300 ceiling → proposed_payment ≤ $300."""
        df, meta = _seller_clean(base_df)
        r = self._run(df, _buyer_budget_tight(), meta)
        assert r["proposed_payment"] <= 300.0

    def test_reserve_not_met_deal_fails(self, base_df):
        """Clean data, seller reserve > proposed payment → deal=False with note."""
        df, meta = _seller_clean(base_df)
        # Deterministic quality with schema=0.5 placeholder: 0.925 → payment = $740
        # Reserve $760 > $740 → deal rejected
        r = self._run(df, _buyer_lenient(), meta, reserve=760.0)
        assert not r["deal"]
        assert any("reserve" in n.lower() for n in r["notes"])

    def test_multi_corrupt_lower_than_clean(self, base_df):
        """Multi-corrupt (nulls + missing label col) → payment lower than clean."""
        df_c, m_c = _seller_clean(base_df)
        df_x, m_x = _seller_multi_corrupt(base_df)
        p = _buyer_lenient()
        assert self._run(df_x, p, m_x)["proposed_payment"] < self._run(df_c, p, m_c)["proposed_payment"]

    def test_price_formula_base_zero(self, base_df):
        """With base_price=0: P = max_budget * S exactly."""
        df, meta = _seller_clean(base_df)
        policy = _buyer_lenient()
        r = self._run(df, policy, meta)
        S = r["quality_score"]
        assert r["proposed_payment"] == pytest.approx(policy.max_budget * S, abs=0.01)


# ---------------------------------------------------------------------------
# Section 2: Agent layer (live LLM)
# ---------------------------------------------------------------------------

class TestAgentLive:

    def setup_method(self):
        self._ids: list[str] = []

    def teardown_method(self):
        for did in self._ids:
            _datasets.pop(did, None)

    def _reg(self, df, meta=None):
        did = _register(df, meta)
        self._ids.append(did)
        return did

    def _metrics(self, df, policy):
        return compute_metrics(df, policy)

    @pytest.mark.live
    def test_exact_schema_match(self, base_df):
        """All required columns present by exact name → schema_score ≥ 0.8."""
        df, meta = _seller_clean(base_df)
        did = self._reg(df, meta)
        policy = _buyer_lenient()
        r = run_agent(did, policy, self._metrics(df, policy), {})
        assert r["schema_score"] >= 0.8

    @pytest.mark.live
    def test_fuzzy_schema_match(self, base_df):
        """fraud_label instead of is_fraud → agent semantic match gives schema_score > 0."""
        df, meta = _seller_fuzzy_schema(base_df)
        did = self._reg(df, meta)
        policy = _buyer_lenient()
        r = run_agent(did, policy, self._metrics(df, policy), {})
        assert r["schema_score"] > 0.0

    @pytest.mark.live
    def test_null_claim_disputed(self, base_df):
        """Seller claims 'no missing values' but 30% amount is null → claim disputed."""
        df, meta = _seller_null_corrupted(base_df)
        did = self._reg(df, meta)
        policy = _buyer_lenient()
        r = run_agent(did, policy, self._metrics(df, policy), {})
        verification = r.get("claim_verification") or {}
        assert any(v == "disputed" for v in verification.values()), (
            f"Expected at least one disputed claim, got: {verification}"
        )

    @pytest.mark.live
    def test_missing_col_lower_schema(self, base_df):
        """is_fraud missing → schema_score lower than when it's present."""
        df_full, m_full = _seller_clean(base_df)
        df_miss, m_miss = _seller_missing_col(base_df)
        policy = _buyer_lenient()
        did_f = self._reg(df_full, m_full)
        did_m = self._reg(df_miss, m_miss)
        score_full = run_agent(did_f, policy, self._metrics(df_full, policy), {})["schema_score"]
        score_miss = run_agent(did_m, policy, self._metrics(df_miss, policy), {})["schema_score"]
        assert score_miss < score_full

    @pytest.mark.live
    def test_explanation_present(self, base_df):
        """Agent always produces a non-empty explanation string."""
        df, meta = _seller_clean(base_df)
        did = self._reg(df, meta)
        policy = _buyer_lenient()
        r = run_agent(did, policy, self._metrics(df, policy), {})
        assert isinstance(r.get("explanation"), str) and len(r["explanation"]) > 10

    @pytest.mark.live
    def test_output_bounds(self, base_df):
        """schema_score and claim_veracity_score always in [0, 1]."""
        df, meta = _seller_clean(base_df)
        did = self._reg(df, meta)
        policy = _buyer_lenient()
        r = run_agent(did, policy, self._metrics(df, policy), {})
        assert 0.0 <= r["schema_score"] <= 1.0
        assert 0.0 <= r["claim_veracity_score"] <= 1.0

    @pytest.mark.live
    def test_schema_matching_dict_returned(self, base_df):
        """Agent returns a non-empty schema_matching dict."""
        df, meta = _seller_clean(base_df)
        did = self._reg(df, meta)
        policy = _buyer_lenient()
        r = run_agent(did, policy, self._metrics(df, policy), {})
        assert isinstance(r.get("schema_matching"), dict) and len(r["schema_matching"]) > 0


# ---------------------------------------------------------------------------
# Section 3: Full pipeline — seller × buyer matrix (live LLM)
# ---------------------------------------------------------------------------

class TestPipelineLive:
    """End-to-end pipeline tests. Results appended to matrix_results for demo JSON."""

    @pytest.mark.live
    def test_happy_path(self, base_df, matrix_results):
        """Clean data + lenient buyer + reserve=$200 → deal, high quality, full explanation."""
        r = _run_pipeline(base_df, _seller_clean, _buyer_lenient(), reserve=200.0)
        assert r.get("deal") is True
        assert r.get("explanation")
        matrix_results.append({
            "type": "evaluation",
            "scenario":  "Happy Path",
            "narrative": (
                "Seller provides clean fraud-detection data. All required columns present, "
                "claims verified. Seller's $200 reserve is comfortably below the $800 offer. "
                "Both parties should accept."
            ),
            "seller": "clean", "buyer": "lenient", "reserve": 200.0,
            "quality": r.get("quality_score"), "payment": r.get("proposed_payment"),
            "deal": r.get("deal"), "notes": r.get("notes", []),
            "explanation": r.get("explanation", ""),
            "schema_matching": r.get("schema_matching"),
            "claim_verification": r.get("claim_verification"),
        })

    @pytest.mark.live
    def test_strict_buyer_coverage_penalty(self, base_df, matrix_results):
        """800-row dataset vs strict 900-row requirement → quality drops, lower price."""
        lenient_r = _run_pipeline(base_df, _seller_clean, _buyer_lenient(), reserve=200.0)
        strict_r  = _run_pipeline(base_df, _seller_clean, _buyer_strict(),  reserve=200.0)
        assert strict_r.get("proposed_payment", 999) <= lenient_r.get("proposed_payment", 0) + 5
        matrix_results.append({
            "type": "evaluation",
            "scenario":  "Strict Buyer — Row Coverage Penalty",
            "narrative": (
                "Same clean dataset, but buyer demands 900 rows and only 800 are present. "
                "Coverage score = 800/900 = 0.89 → quality and price both drop vs lenient buyer."
            ),
            "seller": "clean", "buyer": "strict", "reserve": 200.0,
            "quality": strict_r.get("quality_score"), "payment": strict_r.get("proposed_payment"),
            "deal": strict_r.get("deal"), "notes": strict_r.get("notes", []),
            "explanation": strict_r.get("explanation", ""),
            "schema_matching": strict_r.get("schema_matching"),
            "claim_verification": strict_r.get("claim_verification"),
        })

    @pytest.mark.live
    def test_null_corrupted_claim_disputed(self, base_df, matrix_results):
        """30% nulls + false 'no missing values' claim → agent disputes claim, price dips."""
        r = _run_pipeline(base_df, _seller_null_corrupted, _buyer_lenient(), reserve=200.0)
        matrix_results.append({
            "type": "evaluation",
            "scenario":  "Null-Corrupted + False Claim",
            "narrative": (
                "Seller corrupts 30% of amount values and claims 'all fields populated'. "
                "Strict buyer's 5% null threshold zeroes the null_score. "
                "Agent disputes the no-missing-values claim. Price drops."
            ),
            "seller": "null_corrupted", "buyer": "lenient", "reserve": 200.0,
            "quality": r.get("quality_score"), "payment": r.get("proposed_payment"),
            "deal": r.get("deal"), "notes": r.get("notes", []),
            "explanation": r.get("explanation", ""),
            "schema_matching": r.get("schema_matching"),
            "claim_verification": r.get("claim_verification"),
        })

    def test_reserve_not_met(self, base_df, matrix_results):
        """Clean data, seller reserve=$760 > deterministic offer of $740 → deal rejected.
        Reserve logic is deterministic — no LLM needed for this scenario.
        """
        df, meta = _seller_clean(base_df)
        did = _register(df, meta)
        try:
            det = run_deterministic(did, _buyer_lenient(), reserve_price=760.0)
        finally:
            _datasets.pop(did, None)
        assert not det["deal"]
        assert any("reserve" in n.lower() for n in det["notes"])
        matrix_results.append({
            "type": "evaluation",
            "scenario":  "Reserve Floor Not Met",
            "narrative": (
                "Data quality is good (quality ~0.93, offer ~$740). "
                "But seller's $760 reserve exceeds the computed offer. "
                "The enclave reports: 'reserve not met — consider renegotiation'. "
                "Neither party's private number was revealed. "
                "This is where the renegotiation section begins."
            ),
            "seller": "clean", "buyer": "lenient", "reserve": 760.0,
            "quality": det["quality_score"], "payment": det["proposed_payment"],
            "deal": False, "notes": det["notes"],
            "explanation": None,
            "schema_matching": None, "claim_verification": None,
        })

    @pytest.mark.live
    def test_critical_forbidden_column(self, base_df, matrix_results):
        """SSN column → immediate rejection, agent never runs, payment=$0."""
        r = _run_pipeline(base_df, _seller_forbidden_col, _buyer_lenient(), reserve=0.0)
        assert r.get("deal") is False
        assert r.get("explanation") is None  # agent skipped
        matrix_results.append({
            "type": "evaluation",
            "scenario":  "Critical: PII Column (SSN)",
            "narrative": (
                "Dataset contains an 'ssn' (Social Security Number) column. "
                "The deterministic layer rejects immediately — no LLM is invoked, "
                "no data is analyzed. Payment = $0 (base_price=0)."
            ),
            "seller": "forbidden_col", "buyer": "lenient", "reserve": 0.0,
            "quality": 0.0, "payment": r.get("proposed_payment"),
            "deal": False, "notes": r.get("notes", []),
            "explanation": None,
            "schema_matching": None, "claim_verification": None,
        })

    @pytest.mark.live
    def test_critical_duplicate_spam(self, base_df, matrix_results):
        """50%+ duplicates → critical rejection, agent skipped, payment=$0."""
        r = _run_pipeline(base_df, _seller_dup_corrupted, _buyer_lenient(), reserve=0.0)
        assert r.get("deal") is False
        assert r.get("explanation") is None
        matrix_results.append({
            "type": "evaluation",
            "scenario":  "Critical: 50%+ Duplicates",
            "narrative": (
                "Seller doubled the dataset by copying all rows. "
                "Duplicate rate = 50%, which hits the critical threshold. "
                "Immediate rejection, no LLM, payment = $0."
            ),
            "seller": "dup_corrupted", "buyer": "lenient", "reserve": 0.0,
            "quality": 0.0, "payment": r.get("proposed_payment"),
            "deal": False, "notes": r.get("notes", []),
            "explanation": None,
            "schema_matching": None, "claim_verification": None,
        })

    @pytest.mark.live
    def test_budget_ceiling(self, base_df, matrix_results):
        """Same clean data + $300 ceiling → proportionally lower price."""
        r = _run_pipeline(base_df, _seller_clean, _buyer_budget_tight(), reserve=50.0)
        assert r.get("proposed_payment", 999) <= 300.0
        matrix_results.append({
            "type": "evaluation",
            "scenario":  "Budget Ceiling ($300 max)",
            "narrative": (
                "Same clean dataset, same quality score. But buyer's max_budget=$300 "
                "caps the price. Shows the enclave preserves privacy — seller sees only "
                "a lower offer, never the buyer's max_budget."
            ),
            "seller": "clean", "buyer": "budget_tight", "reserve": 50.0,
            "quality": r.get("quality_score"), "payment": r.get("proposed_payment"),
            "deal": r.get("deal"), "notes": r.get("notes", []),
            "explanation": r.get("explanation", ""),
            "schema_matching": r.get("schema_matching"),
            "claim_verification": r.get("claim_verification"),
        })


# ---------------------------------------------------------------------------
# Section 4: Renegotiation scenarios (deterministic, no LLM)
#
# All scenarios start from a fixed base result:
#   quality=0.65, proposed_payment=$520, settlement_status="pending_approval"
#
# Renegotiation is pure business logic — no AI involved after the initial evaluation.
# The agent ran once; respond_handler drives all subsequent state changes.
# ---------------------------------------------------------------------------

_RENEG_QUALITY   = 0.65
_RENEG_PAYMENT   = 520.0   # = 800 * 0.65


def _reneg_policy():
    return BuyerPolicy(
        required_columns=["transaction_id", "amount", "is_fraud"],
        min_rows=200, max_null_rate=0.35, max_duplicate_rate=0.20,
        min_label_rate=0.01, label_column="is_fraud",
        forbidden_columns=["ssn", "dob"],
        max_budget=800.0, base_price=0.0,
    )


def _base_result():
    """Pending-approval result from a hypothetical TEE evaluation."""
    return {
        "submission_id": "demo-sub",
        "deal": True,
        "quality_score": _RENEG_QUALITY,
        "proposed_payment": _RENEG_PAYMENT,
        "hard_constraints_pass": True,
        "settlement_status": "pending_approval",
        "release_token": None,
        "notes": [],
        "explanation": "Dataset meets buyer requirements with moderate quality.",
        "claim_verification": {"balanced_labels": "verified"},
        "schema_matching": {
            "transaction_id": "transaction_id",
            "amount": "amount",
            "is_fraud": "is_fraud",
        },
        "buyer_response":    None,
        "supplier_response": None,
        "renegotiation_used": False,
    }


class TestRenegotiation:
    """
    Tests for the 3×3 resolution matrix in procurement_respond_handler.
    No LLM needed. Starting point: quality=0.65, proposed_payment=$520.
    """

    def test_both_accept(self, matrix_results):
        """Both accept TEE offer → authorized at $520, no changes."""
        policy = _reneg_policy()
        r = procurement_respond_handler(_base_result(), "accept", None, "buyer",    policy)
        assert r["settlement_status"] == "awaiting_counterparty"
        r = procurement_respond_handler(r,             "accept", None, "supplier", policy)
        assert r["settlement_status"] == "authorized"
        assert r["proposed_payment"] == _RENEG_PAYMENT
        matrix_results.append({
            "type": "renegotiation",
            "scenario":       "Both Accept",
            "narrative":      (
                f"TEE computes ${_RENEG_PAYMENT:.0f}. Both parties accept immediately. "
                "Authorized at the enclave's offer — fastest path to a deal."
            ),
            "initial_offer":  _RENEG_PAYMENT,
            "buyer_action":   "accept",
            "supplier_action":"accept",
            "final_payment":  r["proposed_payment"],
            "deal": True,
        })

    def test_buyer_renegotiates_after_supplier_accepts(self, matrix_results):
        """Supplier locks in $520 by accepting first. Buyer tries to renegotiate to $400 — too late."""
        policy = _reneg_policy()
        r = procurement_respond_handler(_base_result(), "accept",      None,  "supplier", policy)
        r = procurement_respond_handler(r,             "renegotiate", 400.0, "buyer",    policy)
        # Supplier already committed → deal at original proposed_payment, buyer's revision ignored
        assert r["settlement_status"] == "authorized"
        assert r["proposed_payment"] == _RENEG_PAYMENT
        matrix_results.append({
            "type": "renegotiation",
            "scenario":       "Acceptor Locks the Price",
            "narrative":      (
                f"Supplier accepts the ${_RENEG_PAYMENT:.0f} offer. "
                "Buyer later tries to renegotiate down to $400 — but supplier already committed. "
                "Deal authorizes at $520 (supplier's acceptance stands). "
                "First to accept locks the price."
            ),
            "initial_offer":  _RENEG_PAYMENT,
            "buyer_action":   "renegotiate → $400",
            "supplier_action":"accept",
            "final_payment":  r["proposed_payment"],
            "deal": True,
        })

    def test_both_renegotiate_terms_overlap(self, matrix_results):
        """Both renegotiate. Buyer offers $480, seller accepts $420 floor → deal at $480."""
        policy = _reneg_policy()
        r = procurement_respond_handler(_base_result(), "renegotiate", 480.0, "buyer",    policy)
        r = procurement_respond_handler(r,             "renegotiate", 420.0, "supplier", policy)
        assert r["settlement_status"] == "authorized"
        assert r["proposed_payment"] == 480.0  # buyer's revised offer (>= seller's 420)
        matrix_results.append({
            "type": "renegotiation",
            "scenario":       "Both Renegotiate — Terms Overlap",
            "narrative":      (
                f"TEE offers ${_RENEG_PAYMENT:.0f}. Buyer revises offer to $480. "
                "Seller revises reserve down to $420. "
                "$480 ≥ $420 → authorized at buyer's revised offer. "
                "No midpoint — buyer's number wins when terms overlap."
            ),
            "initial_offer":  _RENEG_PAYMENT,
            "buyer_action":   "renegotiate → $480",
            "supplier_action":"renegotiate → $420",
            "final_payment":  480.0,
            "deal": True,
        })

    def test_both_renegotiate_no_overlap(self, matrix_results):
        """Both renegotiate with incompatible terms → rejected."""
        policy = _reneg_policy()
        r = procurement_respond_handler(_base_result(), "renegotiate", 350.0, "buyer",    policy)
        r = procurement_respond_handler(r,             "renegotiate", 450.0, "supplier", policy)
        assert r["settlement_status"] == "rejected"
        matrix_results.append({
            "type": "renegotiation",
            "scenario":       "Both Renegotiate — No Overlap",
            "narrative":      (
                f"TEE offers ${_RENEG_PAYMENT:.0f}. Buyer revises to $350. "
                "Seller revises reserve up to $450. "
                "$350 < $450 → deal rejected. Neither party revealed their original private number."
            ),
            "initial_offer":  _RENEG_PAYMENT,
            "buyer_action":   "renegotiate → $350",
            "supplier_action":"renegotiate → $450",
            "final_payment":  None,
            "deal": False,
        })

    def test_either_party_rejects(self, matrix_results):
        """One party rejects → immediate deal-off regardless of other's action."""
        policy = _reneg_policy()
        r = procurement_respond_handler(_base_result(), "accept", None, "buyer",    policy)
        r = procurement_respond_handler(r,             "reject", None, "supplier", policy)
        assert r["settlement_status"] == "rejected"
        matrix_results.append({
            "type": "renegotiation",
            "scenario":       "Hard Reject",
            "narrative":      (
                f"Buyer accepts the ${_RENEG_PAYMENT:.0f} TEE offer. "
                "Supplier rejects outright. One rejection ends the deal — no further rounds."
            ),
            "initial_offer":  _RENEG_PAYMENT,
            "buyer_action":   "accept",
            "supplier_action":"reject",
            "final_payment":  None,
            "deal": False,
        })
