"""
E2E tests for the confidential_data_procurement skill.

Validates API plumbing: token auth, upload, submit, role-filtered results,
deal responses, and renegotiation. LLM + deterministic pipeline are mocked
so no API keys or credits are needed.

Scenarios:
    1. Happy path: init → register → upload → submit → accept → authorized
    2. Critical reject: forbidden column CSV → immediate rejection, no LLM
    3. Role filtering: buyer sees quality_score, supplier does not
    4. Renegotiate: double-renegotiate with overlapping terms → authorized
    5. Mixed respond: buyer accept + supplier renegotiate → authorized
    6. Token enforcement: missing/invalid token → 401/403
"""
from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch

import api.routes as routes
from core.models import SkillResponse
from skills.confidential_data_procurement import skill_card as proc_card
from skills.confidential_data_procurement.models import BuyerPolicy


# ---------------------------------------------------------------------------
# Test data
# ---------------------------------------------------------------------------

_GOOD_CSV = (
    b"transaction_id,amount,is_fraud\n"
    + b"".join(
        f"txn_{i:04d},{i * 10.5:.2f},{1 if i % 25 == 0 else 0}\n".encode()
        for i in range(200)
    )
)

_BAD_CSV = (
    b"transaction_id,amount,is_fraud,ssn\n"
    + b"".join(
        f"txn_{i:04d},{i * 10.5:.2f},{1 if i % 25 == 0 else 0},xxx-xx-0000\n".encode()
        for i in range(50)
    )
)

_METADATA_JSON = json.dumps({
    "column_definitions": {
        "transaction_id": "Unique ID for each transaction",
        "amount": "Transaction amount in USD",
        "is_fraud": "1 if fraudulent, 0 otherwise",
    },
    "seller_claims": {
        "balanced_labels": "Approximately 4% fraud rate",
        "no_missing_values": "All fields fully populated",
    },
}).encode()

_POLICY = BuyerPolicy(
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


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------

def _make_init_handler(policy: BuyerPolicy = _POLICY):
    """Stateful mock: turn 1 → configuring, turn 2 → ready with BuyerPolicy."""
    calls = []

    def handler(message, conversation):
        calls.append(message)
        conv = list(conversation) + [{"role": "human", "content": message}]
        if len(calls) == 1:
            conv.append({"role": "ai", "content": "Please describe your dataset requirements."})
            return {
                "status": "configuring",
                "message": "Please describe your dataset requirements.",
                "conversation": conv,
            }
        conv.append({"role": "ai", "content": "Policy saved."})
        return {
            "status": "ready",
            "message": "Policy saved.",
            "conversation": conv,
            "config": policy,
            "threshold": 1,
        }

    return handler


def _fake_run_deal(inputs, params):
    return SkillResponse(
        skill="confidential_data_procurement",
        results=[{
            "submission_id": inputs[0].submission_id,
            "deal": True,
            "quality_score": 0.82,
            "proposed_payment": 3500.0,
            "hard_constraints_pass": True,
            "settlement_status": "pending_approval",
            "release_token": None,
            "notes": [],
            "explanation": "Dataset meets all requirements.",
            "claim_verification": {"balanced_labels": "verified"},
            "schema_matching": {"transaction_id": "transaction_id"},
            "buyer_response": None,
            "supplier_response": None,
            "renegotiation_used": False,
        }],
    )


def _fake_run_rejected(inputs, params):
    return SkillResponse(
        skill="confidential_data_procurement",
        results=[{
            "submission_id": inputs[0].submission_id,
            "deal": False,
            "quality_score": 0.0,
            "proposed_payment": 500.0,
            "hard_constraints_pass": False,
            "settlement_status": "rejected",
            "release_token": None,
            "notes": ["Forbidden column 'ssn' detected. Deal rejected."],
            "explanation": None,
            "claim_verification": None,
            "schema_matching": None,
            "buyer_response": None,
            "supplier_response": None,
            "renegotiation_used": False,
        }],
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def clear_stores():
    """Reset all in-memory state before each test."""
    routes._instances.clear()
    routes._submissions.clear()
    routes._results.clear()
    routes._tokens.clear()
    routes._registrations.clear()
    from skills.confidential_data_procurement.ingest import _datasets
    _datasets.clear()
    yield
    _datasets.clear()


@pytest.fixture
def client():
    from main import app
    return TestClient(app)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _init_procurement(client, policy=_POLICY):
    """Run the two-turn init flow and return (instance_id, admin_token)."""
    handler = _make_init_handler(policy)
    with patch.object(proc_card, "init_handler", handler):
        r = client.post("/init", json={"skill_name": "confidential_data_procurement", "message": "setup"})
        assert r.status_code == 200
        instance_id = r.json()["instance_id"]

        r = client.post("/init", json={
            "skill_name": "confidential_data_procurement",
            "message": "transaction_id, amount, is_fraud, budget 5000",
            "instance_id": instance_id,
        })
        assert r.status_code == 200
        assert r.json()["status"] == "ready"
        return instance_id, r.json()["admin_token"]


def _register(client, instance_id):
    r = client.post("/register", json={"instance_id": instance_id})
    assert r.status_code == 200
    return r.json()["user_token"]


def _upload(client, user_token, csv_bytes=_GOOD_CSV, metadata_bytes=_METADATA_JSON):
    r = client.post(
        "/upload",
        files={
            "csv_file": ("dataset.csv", csv_bytes, "text/csv"),
            "metadata_file": ("metadata.json", metadata_bytes, "application/json"),
        },
        headers={"X-Instance-Token": user_token},
    )
    assert r.status_code == 200, r.text
    return r.json()["dataset_id"]


def _submit(client, user_token, dataset_id, sub_id="sub-001", reserve=1000.0):
    r = client.post(
        "/submit",
        json={
            "submission_id": sub_id,
            "dataset_id": dataset_id,
            "dataset_name": "fraud_dataset.csv",
            "reserve_price": reserve,
        },
        headers={"X-Instance-Token": user_token},
    )
    assert r.status_code == 200
    return r.json()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_procurement_happy_path_both_accept(client):
    """Full happy path: init → upload → submit → both accept → authorized."""
    instance_id, admin_token = _init_procurement(client)
    user_token = _register(client, instance_id)
    dataset_id = _upload(client, user_token)

    with patch.object(proc_card, "run", _fake_run_deal):
        resp = _submit(client, user_token, dataset_id)
    assert resp["status"] == "received_analysis_complete"

    # Buyer views result (should see quality_score)
    r = client.get("/results/sub-001", headers={"X-Instance-Token": admin_token})
    assert r.status_code == 200
    result = r.json()
    assert result["deal"] is True
    assert "quality_score" in result
    assert result["settlement_status"] == "pending_approval"

    # Buyer accepts
    r = client.post("/respond", json={
        "submission_id": "sub-001",
        "action": "accept",
    }, headers={"X-Instance-Token": admin_token})
    assert r.status_code == 200
    assert r.json()["settlement_status"] == "awaiting_counterparty"

    # Supplier accepts
    r = client.post("/respond", json={
        "submission_id": "sub-001",
        "action": "accept",
    }, headers={"X-Instance-Token": user_token})
    assert r.status_code == 200
    assert r.json()["settlement_status"] == "authorized"

    # Final result should have release_token
    r = client.get("/results/sub-001", headers={"X-Instance-Token": admin_token})
    assert r.json()["release_token"] is not None
    assert r.json()["settlement_status"] == "authorized"


def test_procurement_critical_reject(client):
    """Forbidden column CSV → settlement_status='rejected' immediately."""
    instance_id, admin_token = _init_procurement(client)
    user_token = _register(client, instance_id)
    dataset_id = _upload(client, user_token, csv_bytes=_BAD_CSV)

    with patch.object(proc_card, "run", _fake_run_rejected):
        _submit(client, user_token, dataset_id)

    r = client.get("/results/sub-001", headers={"X-Instance-Token": admin_token})
    assert r.status_code == 200
    result = r.json()
    assert result["deal"] is False
    assert result["settlement_status"] == "rejected"
    assert len(result["notes"]) > 0


def test_procurement_role_filtering(client):
    """Buyer sees quality_score; supplier does not."""
    instance_id, admin_token = _init_procurement(client)
    user_token = _register(client, instance_id)
    dataset_id = _upload(client, user_token)

    with patch.object(proc_card, "run", _fake_run_deal):
        _submit(client, user_token, dataset_id)

    buyer_result = client.get(
        "/results/sub-001", headers={"X-Instance-Token": admin_token}
    ).json()
    supplier_result = client.get(
        "/results/sub-001", headers={"X-Instance-Token": user_token}
    ).json()

    assert "quality_score" in buyer_result
    assert "hard_constraints_pass" in buyer_result
    assert "quality_score" not in supplier_result
    assert "hard_constraints_pass" not in supplier_result

    # Both should see proposed_payment and deal
    assert "proposed_payment" in supplier_result
    assert "deal" in supplier_result


def test_procurement_double_renegotiate_success(client):
    """Both renegotiate with overlapping terms → authorized."""
    instance_id, admin_token = _init_procurement(client)
    user_token = _register(client, instance_id)
    dataset_id = _upload(client, user_token)

    with patch.object(proc_card, "run", _fake_run_deal):
        _submit(client, user_token, dataset_id)

    # Buyer renegotiates down to 3000
    r = client.post("/respond", json={
        "submission_id": "sub-001",
        "action": "renegotiate",
        "revised_value": 3000.0,
    }, headers={"X-Instance-Token": admin_token})
    assert r.status_code == 200
    assert r.json()["settlement_status"] == "awaiting_counterparty"

    # Supplier renegotiates reserve down to 2500 (< buyer's 3000 → deal)
    r = client.post("/respond", json={
        "submission_id": "sub-001",
        "action": "renegotiate",
        "revised_value": 2500.0,
    }, headers={"X-Instance-Token": user_token})
    assert r.status_code == 200
    assert r.json()["settlement_status"] == "authorized"

    r = client.get("/results/sub-001", headers={"X-Instance-Token": admin_token})
    assert r.json()["proposed_payment"] == 3000.0


def test_procurement_double_renegotiate_failure(client):
    """Both renegotiate but terms don't meet → rejected."""
    instance_id, admin_token = _init_procurement(client)
    user_token = _register(client, instance_id)
    dataset_id = _upload(client, user_token)

    with patch.object(proc_card, "run", _fake_run_deal):
        _submit(client, user_token, dataset_id)

    client.post("/respond", json={
        "submission_id": "sub-001", "action": "renegotiate", "revised_value": 1000.0,
    }, headers={"X-Instance-Token": admin_token})

    r = client.post("/respond", json={
        "submission_id": "sub-001", "action": "renegotiate", "revised_value": 2000.0,
    }, headers={"X-Instance-Token": user_token})
    assert r.json()["settlement_status"] == "rejected"


def test_procurement_buyer_accept_supplier_renegotiate(client):
    """Buyer accepts, supplier renegotiates → authorized (acceptor's bound honored)."""
    instance_id, admin_token = _init_procurement(client)
    user_token = _register(client, instance_id)
    dataset_id = _upload(client, user_token)

    with patch.object(proc_card, "run", _fake_run_deal):
        _submit(client, user_token, dataset_id)

    client.post("/respond", json={
        "submission_id": "sub-001", "action": "accept",
    }, headers={"X-Instance-Token": admin_token})

    r = client.post("/respond", json={
        "submission_id": "sub-001", "action": "renegotiate", "revised_value": 4000.0,
    }, headers={"X-Instance-Token": user_token})
    assert r.json()["settlement_status"] == "authorized"


def test_procurement_second_renegotiation_rejected(client):
    """Second renegotiation attempt returns 422."""
    instance_id, admin_token = _init_procurement(client)
    user_token = _register(client, instance_id)
    dataset_id = _upload(client, user_token)

    with patch.object(proc_card, "run", _fake_run_deal):
        _submit(client, user_token, dataset_id)

    # First renegotiation
    client.post("/respond", json={
        "submission_id": "sub-001", "action": "renegotiate", "revised_value": 3000.0,
    }, headers={"X-Instance-Token": admin_token})
    client.post("/respond", json={
        "submission_id": "sub-001", "action": "renegotiate", "revised_value": 2500.0,
    }, headers={"X-Instance-Token": user_token})

    # Attempt second renegotiation — should fail
    r = client.post("/respond", json={
        "submission_id": "sub-001", "action": "renegotiate", "revised_value": 2000.0,
    }, headers={"X-Instance-Token": admin_token})
    assert r.status_code == 422


def test_procurement_missing_token_401(client):
    """No token header → 401."""
    r = client.post("/submit", json={
        "submission_id": "sub-001", "dataset_id": "x",
        "dataset_name": "x.csv", "reserve_price": 100.0,
    })
    assert r.status_code == 401


def test_procurement_user_cannot_see_other_submission(client):
    """User token cannot view a result it didn't submit."""
    instance_id, admin_token = _init_procurement(client)
    user_a = _register(client, instance_id)
    user_b = _register(client, instance_id)

    dataset_id = _upload(client, user_a)
    with patch.object(proc_card, "run", _fake_run_deal):
        _submit(client, user_a, dataset_id, sub_id="sub-a")

    r = client.get("/results/sub-a", headers={"X-Instance-Token": user_b})
    assert r.status_code == 403


def test_procurement_upload_without_csv_returns_422(client):
    """Upload with no csv_file field → 422."""
    instance_id, _ = _init_procurement(client)
    user_token = _register(client, instance_id)

    r = client.post(
        "/upload",
        files={"metadata_file": ("meta.json", b"{}", "application/json")},
        headers={"X-Instance-Token": user_token},
    )
    assert r.status_code == 422


def test_procurement_skill_appears_in_skills_list(client):
    """New skill is registered and visible via GET /skills."""
    r = client.get("/skills")
    assert r.status_code == 200
    names = [s["name"] for s in r.json()["skills"]]
    assert "confidential_data_procurement" in names
