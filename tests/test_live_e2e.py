"""
Live E2E tests for confidential_data_procurement.

Tests the full API endpoint flow with real HuggingFace transaction data and a real LLM.
No hardcoded BuyerPolicy — buyer describes requirements in natural language via POST /init.

Scenarios:
    1. Full satisfaction   — clean seller data, all required columns → deal, both accept
    2. Partial satisfaction — seller drops 'category' → lower payment (schema gap flagged)
    3. Bad data            — >50% duplicate rows → critical rejection, no LLM agent ran
    4. Renegotiation overlap   — partial data, both negotiate, terms meet → authorized
    5. Renegotiation no overlap — partial data, buyer drops 40%, seller holds → rejected

NOTE: All tests are @pytest.mark.live. They are skipped unless CONCLAVE_NEARAI_API_KEY
is set in the environment. Run individually with:
    set -a && source .env && set +a
    ./venv/bin/python -m pytest tests/test_live_e2e.py -v -s
"""
from __future__ import annotations

import json
import uuid

import pandas as pd
import pytest
from fastapi.testclient import TestClient

import api.routes as routes
from skills.confidential_data_procurement.ingest import _datasets


# ---------------------------------------------------------------------------
# Buyer prompt — natural language, ~150 words, all required fields included
# ---------------------------------------------------------------------------

BUYER_PROMPT = (
    "We are building a machine learning pipeline for real-time fraud detection in "
    "payment processing. We need a labeled transaction dataset with four specific columns: "
    "transaction_id (a unique identifier per transaction), amount (the transaction value "
    "in USD), is_fraud (a binary label — 1 for fraudulent, 0 for legitimate), and category "
    "(merchant category code). The dataset must contain at least 500 rows. We can tolerate "
    "at most 5% missing values and at most 10% duplicate rows. No personally identifiable "
    "information should appear — date of birth, credit card numbers, social security numbers, "
    "or any customer names and addresses are strictly not acceptable. This data will train a "
    "gradient boosting classifier so label accuracy and field completeness are critical. "
    "Our maximum budget for a perfect dataset is $800. We have no floor price — if the "
    "data is unusable we expect to pay nothing."
)


# ---------------------------------------------------------------------------
# Seller metadata
# ---------------------------------------------------------------------------

_META_CLEAN = json.dumps({
    "column_definitions": {
        "transaction_id": "Unique identifier per transaction",
        "amount":         "Transaction value in USD",
        "is_fraud":       "Binary fraud label — 1 if fraudulent, 0 otherwise",
        "category":       "Merchant category code",
    },
    "seller_claims": {
        "completeness": "All four columns are fully populated — zero missing values",
        "label_rate":   "Approximately 4% of transactions are labeled as fraudulent",
    },
}).encode()

_META_PARTIAL = json.dumps({
    "column_definitions": {
        "transaction_id": "Unique identifier per transaction",
        "amount":         "Transaction value in USD",
        "is_fraud":       "Binary fraud label",
    },
    "seller_claims": {
        "completeness": "Data is mostly complete",
    },
}).encode()


# ---------------------------------------------------------------------------
# Session fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def app_client():
    """Session-scoped TestClient — state persists across all live E2E tests."""
    # Clear any leftover state from prior test files
    routes._instances.clear()
    routes._submissions.clear()
    routes._results.clear()
    routes._tokens.clear()
    routes._registrations.clear()
    _datasets.clear()
    from main import app
    with TestClient(app) as client:
        yield client
    _datasets.clear()


@pytest.fixture(scope="session")
def buyer_init(app_client):
    """
    Single real LLM conversation: buyer describes requirements → BuyerPolicy extracted.
    Session-scoped — runs once, all scenario tests share the same instance.
    """
    r1 = app_client.post("/init", json={
        "skill_name": "confidential_data_procurement",
        "message": "I want to set up a data procurement instance.",
    })
    assert r1.status_code == 200, r1.text
    instance_id = r1.json()["instance_id"]

    r2 = app_client.post("/init", json={
        "skill_name": "confidential_data_procurement",
        "message": BUYER_PROMPT,
        "instance_id": instance_id,
    })
    assert r2.status_code == 200, r2.text

    # If LLM asks a follow-up, give one more nudge
    if r2.json().get("status") != "ready":
        r3 = app_client.post("/init", json={
            "skill_name": "confidential_data_procurement",
            "message": "That covers everything. Please finalize the policy.",
            "instance_id": instance_id,
        })
        assert r3.status_code == 200, r3.text
        assert r3.json().get("status") == "ready", (
            f"Init handler did not reach ready after 3 turns: {r3.json().get('message')}"
        )
        admin_token = r3.json()["admin_token"]
    else:
        admin_token = r2.json()["admin_token"]

    print(f"\n[buyer_init] instance_id={instance_id}, admin_token={admin_token[:12]}...")
    return instance_id, admin_token


# ---------------------------------------------------------------------------
# Seller data builders (from real HuggingFace base_df)
# ---------------------------------------------------------------------------

def _clean_csv(base_df: pd.DataFrame) -> bytes:
    """All four required columns, no corruption."""
    cols = [c for c in ["transaction_id", "amount", "is_fraud", "category"]
            if c in base_df.columns]
    return base_df[cols].to_csv(index=False).encode()


def _partial_csv(base_df: pd.DataFrame) -> bytes:
    """Drop 'category' — buyer requires it. Everything else intact."""
    cols = [c for c in ["transaction_id", "amount", "is_fraud"]
            if c in base_df.columns]
    return base_df[cols].to_csv(index=False).encode()


def _bad_csv(base_df: pd.DataFrame) -> bytes:
    """Duplicate every row — produces exactly 50% dup rate, triggers critical rejection."""
    cols = [c for c in ["transaction_id", "amount", "is_fraud", "category"]
            if c in base_df.columns]
    df = base_df[cols]
    return pd.concat([df, df]).to_csv(index=False).encode()


# ---------------------------------------------------------------------------
# API helpers
# ---------------------------------------------------------------------------

def _register(client, instance_id: str) -> str:
    r = client.post("/register", json={"instance_id": instance_id})
    assert r.status_code == 200, r.text
    return r.json()["user_token"]


def _upload(client, user_token: str, csv_bytes: bytes, metadata_bytes: bytes) -> str:
    r = client.post(
        "/upload",
        files={
            "csv_file":      ("dataset.csv",   csv_bytes,      "text/csv"),
            "metadata_file": ("metadata.json", metadata_bytes, "application/json"),
        },
        headers={"X-Instance-Token": user_token},
    )
    assert r.status_code == 200, r.text
    return r.json()["dataset_id"]


def _submit(client, user_token: str, dataset_id: str, sub_id: str, reserve: float) -> dict:
    r = client.post(
        "/submit",
        json={
            "submission_id": sub_id,
            "dataset_id":    dataset_id,
            "dataset_name":  "seller_data.csv",
            "reserve_price": reserve,
        },
        headers={"X-Instance-Token": user_token},
    )
    assert r.status_code == 200, r.text
    return r.json()


def _get_result(client, sub_id: str, token: str) -> dict:
    r = client.get(f"/results/{sub_id}", headers={"X-Instance-Token": token})
    assert r.status_code == 200, r.text
    return r.json()


def _respond(client, sub_id: str, action: str, token: str,
             revised_value: float | None = None) -> dict:
    body: dict = {"submission_id": sub_id, "action": action}
    if revised_value is not None:
        body["revised_value"] = revised_value
    r = client.post("/respond", json=body, headers={"X-Instance-Token": token})
    assert r.status_code == 200, r.text
    return r.json()


def _run_pipeline(client, buyer_init, csv_bytes: bytes, metadata_bytes: bytes,
                  reserve: float):
    """
    Full supplier flow: register → upload → submit → get_result.
    Returns (result_dict, admin_token, user_token, sub_id).
    """
    instance_id, admin_token = buyer_init
    user_token = _register(client, instance_id)
    dataset_id = _upload(client, user_token, csv_bytes, metadata_bytes)
    sub_id     = str(uuid.uuid4())[:12]
    _submit(client, user_token, dataset_id, sub_id, reserve)
    result = _get_result(client, sub_id, admin_token)
    print(f"\n  pipeline → sub={sub_id} deal={result.get('deal')} "
          f"quality={result.get('quality_score')} payment=${result.get('proposed_payment')}")
    return result, admin_token, user_token, sub_id


# ---------------------------------------------------------------------------
# Scenario 1: Full satisfaction
# ---------------------------------------------------------------------------

@pytest.mark.live
def test_full_satisfaction(app_client, base_df, buyer_init, matrix_results):
    """
    100% satisfied: clean data, all required columns, honest claims.
    Both parties accept the enclave's offer → authorized.
    """
    result, admin_token, user_token, sub_id = _run_pipeline(
        app_client, buyer_init,
        _clean_csv(base_df), _META_CLEAN, reserve=150.0,
    )

    assert result.get("deal") is True, f"Expected deal=True, got: {result}"
    assert result.get("settlement_status") == "pending_approval"

    _respond(app_client, sub_id, "accept", admin_token)
    respond_result = _respond(app_client, sub_id, "accept", user_token)
    assert respond_result["settlement_status"] == "authorized"

    # Fetch full result to verify release_token issued
    final = _get_result(app_client, sub_id, admin_token)
    assert final.get("release_token") is not None

    matrix_results.append({
        "type":     "evaluation",
        "scenario": "Full Satisfaction",
        "narrative": (
            "Buyer described exact requirements in natural language — LLM extracted the policy. "
            "Seller uploaded clean real transaction data (HuggingFace) with all four required columns. "
            "Agent verified claims and found no schema gaps. Both parties accepted the enclave's offer."
        ),
        "buyer_prompt": BUYER_PROMPT,
        "seller_input": {
            "column_definitions": {
                "transaction_id": "Unique identifier per transaction",
                "amount":         "Transaction value in USD",
                "is_fraud":       "Binary fraud label — 1 if fraudulent, 0 otherwise",
                "category":       "Merchant category code",
            },
            "seller_claims": {
                "completeness": "All four columns are fully populated — zero missing values",
                "label_rate":   "Approximately 4% of transactions are labeled as fraudulent",
            },
        },
        "seller":  "clean",
        "buyer":   "standard ($800)",
        "reserve": 150.0,
        "quality": result.get("quality_score"),
        "payment": result.get("proposed_payment"),
        "deal":    True,
        "notes":              result.get("notes", []),
        "explanation":        result.get("explanation", ""),
        "schema_matching":    result.get("schema_matching"),
        "claim_verification": result.get("claim_verification"),
    })


# ---------------------------------------------------------------------------
# Scenario 2: Partial satisfaction
# ---------------------------------------------------------------------------

@pytest.mark.live
def test_partial_satisfaction(app_client, base_df, buyer_init, matrix_results):
    """
    ~80% satisfied: seller drops 'category' (buyer required it).
    Agent penalises schema score — payment is proportionally lower.
    """
    result, _, _, _ = _run_pipeline(
        app_client, buyer_init,
        _partial_csv(base_df), _META_PARTIAL, reserve=50.0,
    )

    # Agent should at minimum note the missing column in its explanation
    explanation = result.get("explanation", "")
    assert "category" in explanation.lower(), (
        f"Expected agent to flag missing 'category' column. Explanation: {explanation}"
    )

    matrix_results.append({
        "type":     "evaluation",
        "scenario": "Partial Satisfaction",
        "narrative": (
            "Seller omitted the 'category' column, which the buyer explicitly required. "
            "Agent identified the schema gap and noted it in the explanation. "
            "Quality score and payment reflect the LLM's assessment of the partial dataset."
        ),
        "buyer_prompt": BUYER_PROMPT,
        "seller_input": {
            "column_definitions": {
                "transaction_id": "Unique identifier per transaction",
                "amount":         "Transaction value in USD",
                "is_fraud":       "Binary fraud label",
            },
            "seller_claims": {
                "completeness": "Data is mostly complete",
            },
        },
        "seller":  "partial (missing category)",
        "buyer":   "standard ($800)",
        "reserve": 50.0,
        "quality": result.get("quality_score"),
        "payment": result.get("proposed_payment"),
        "deal":    result.get("deal"),
        "notes":              result.get("notes", []),
        "explanation":        result.get("explanation", ""),
        "schema_matching":    result.get("schema_matching"),
        "claim_verification": result.get("claim_verification"),
    })


# ---------------------------------------------------------------------------
# Scenario 3: Bad data — critical rejection
# ---------------------------------------------------------------------------

@pytest.mark.live
def test_bad_data_rejected(app_client, base_df, buyer_init, matrix_results):
    """
    Critical: >50% duplicate rows → immediate rejection by deterministic layer.
    No LLM agent ran — explanation is absent.
    """
    result, _, _, _ = _run_pipeline(
        app_client, buyer_init,
        _bad_csv(base_df), _META_CLEAN, reserve=0.0,
    )

    assert result.get("deal") is False
    assert not result.get("explanation"), "Agent should not have run for critical rejection"

    matrix_results.append({
        "type":     "evaluation",
        "scenario": "Critical: >50% Duplicates",
        "narrative": (
            "Seller submitted a dataset where every row is duplicated — over 50% dup rate. "
            "The deterministic layer flags this as a critical violation and rejects immediately. "
            "No LLM call. Payment = $0. Seller's reserve price is irrelevant."
        ),
        "buyer_prompt": BUYER_PROMPT,
        "seller_input": {
            "column_definitions": {
                "transaction_id": "Unique identifier per transaction",
                "amount":         "Transaction value in USD",
                "is_fraud":       "Binary fraud label — 1 if fraudulent, 0 otherwise",
                "category":       "Merchant category code",
            },
            "seller_claims": {},
            "note": "Every row duplicated — submitted 2000 rows from a 1000-row base dataset",
        },
        "seller":  "duplicated (>50%)",
        "buyer":   "standard ($800)",
        "reserve": 0.0,
        "quality": 0.0,
        "payment": result.get("proposed_payment", 0),
        "deal":    False,
        "notes":              result.get("notes", []),
        "explanation":        None,
        "schema_matching":    None,
        "claim_verification": None,
    })


# ---------------------------------------------------------------------------
# Scenario 4: Renegotiation — terms overlap → deal
# ---------------------------------------------------------------------------

@pytest.mark.live
def test_renegotiation_overlap(app_client, base_df, buyer_init, matrix_results):
    """
    Partial data evaluated by full pipeline. Enclave proposes an offer.
    Buyer revises down 12%, seller lowers floor 21% — they overlap → deal.
    Amounts derived from the actual pipeline result (no hardcoding).
    """
    result, admin_token, user_token, sub_id = _run_pipeline(
        app_client, buyer_init,
        _partial_csv(base_df), _META_PARTIAL, reserve=50.0,
    )
    assert result.get("settlement_status") == "pending_approval", (
        f"Expected pending_approval for renegotiation test, got: {result.get('settlement_status')}"
    )

    p = result["proposed_payment"]
    buyer_revised    = round(p * 0.88)   # buyer cuts 12%
    supplier_revised = round(p * 0.79)   # seller lowers floor 21%

    _respond(app_client, sub_id, "renegotiate", admin_token,  buyer_revised)
    respond_result = _respond(app_client, sub_id, "renegotiate", user_token, supplier_revised)
    assert respond_result["settlement_status"] == "authorized", (
        f"Expected authorized, got: {respond_result['settlement_status']}. "
        f"buyer_revised={buyer_revised}, supplier_revised={supplier_revised}"
    )

    # Fetch full result to verify final payment
    final = _get_result(app_client, sub_id, admin_token)
    assert final["proposed_payment"] == buyer_revised

    matrix_results.append({
        "type":     "renegotiation",
        "scenario": "Renegotiation — Terms Overlap",
        "narrative": (
            f"Enclave offers ${p:.0f} for partial data (missing category). "
            f"Buyer revises down to ${buyer_revised:.0f} (−12%). "
            f"Seller lowers floor to ${supplier_revised:.0f} (−21%). "
            f"${buyer_revised:.0f} ≥ ${supplier_revised:.0f} → deal at buyer's revised offer. "
            "Neither party saw the other's private number."
        ),
        "initial_offer":   p,
        "buyer_action":    f"renegotiate → ${buyer_revised:.0f}",
        "supplier_action": f"renegotiate → ${supplier_revised:.0f}",
        "final_payment":   buyer_revised,
        "deal":            True,
    })


# ---------------------------------------------------------------------------
# Scenario 5: Renegotiation — no overlap → rejected
# ---------------------------------------------------------------------------

@pytest.mark.live
def test_renegotiation_no_overlap(app_client, base_df, buyer_init, matrix_results):
    """
    Partial data evaluated. Buyer drops 40%, seller barely moves (−5%).
    No overlap → deal rejected. One renegotiation round used, deal falls through.
    """
    result, admin_token, user_token, sub_id = _run_pipeline(
        app_client, buyer_init,
        _partial_csv(base_df), _META_PARTIAL, reserve=50.0,
    )
    assert result.get("settlement_status") == "pending_approval", (
        f"Expected pending_approval for renegotiation test, got: {result.get('settlement_status')}"
    )

    p = result["proposed_payment"]
    buyer_revised    = round(p * 0.60)   # buyer drops 40%
    supplier_revised = round(p * 0.95)   # seller barely moves

    _respond(app_client, sub_id, "renegotiate", admin_token,  buyer_revised)
    final = _respond(app_client, sub_id, "renegotiate", user_token, supplier_revised)

    assert final["settlement_status"] == "rejected", (
        f"Expected rejected, got: {final['settlement_status']}. "
        f"buyer_revised={buyer_revised}, supplier_revised={supplier_revised}"
    )

    matrix_results.append({
        "type":     "renegotiation",
        "scenario": "Renegotiation — No Overlap",
        "narrative": (
            f"Enclave offers ${p:.0f} for partial data. "
            f"Buyer drops hard to ${buyer_revised:.0f} (−40%). "
            f"Seller holds firm at ${supplier_revised:.0f} (−5%). "
            f"${buyer_revised:.0f} < ${supplier_revised:.0f} → deal falls through. "
            "One round used — both sides walked away."
        ),
        "initial_offer":   p,
        "buyer_action":    f"renegotiate → ${buyer_revised:.0f}",
        "supplier_action": f"renegotiate → ${supplier_revised:.0f}",
        "final_payment":   None,
        "deal":            False,
    })
