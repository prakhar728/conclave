"""
E2E tests for the full Conclave API workflow.

Validates API plumbing — token auth, role enforcement, auto-trigger logic,
and result routing. LLM calls are mocked: no API keys or credits needed.
This is the CI test suite.

Workflow covered:
    1. Operator init (multi-turn loop) → configuring → ready, tokens issued
    2. Participant submits below threshold → received_pending
    3. 5th submission auto-triggers pipeline → received_analysis_complete
    4. Operator manual trigger → runs pipeline
    5. Role-based result views (admin sees all, user sees own)
    6. Token enforcement (missing/wrong/wrong-role → 401/403)
"""
from __future__ import annotations
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient

import api.routes as routes
from core.models import OperatorConfig, SkillResponse
from skills.hackathon_novelty import skill_card


# --- Fakes ---

def _fake_run_skill(inputs, params):
    """Returns a deterministic SkillResponse for any list of HackathonSubmission inputs."""
    return SkillResponse(
        skill="hackathon_novelty",
        results=[
            {
                "submission_id": s.submission_id,
                "novelty_score": 0.7,
                "percentile": 60.0,
                "cluster": "A",
                "criteria_scores": {"originality": 7.0, "feasibility": 6.0},
                "status": "analyzed",
                "analysis_depth": "full",
                "duplicate_of": None,
            }
            for s in inputs
        ],
    )


def _make_init_handler():
    """Stateful handler: call 1 → configuring, call 2 → ready."""
    calls = []

    def handler(message, conversation):
        calls.append(message)
        conv = list(conversation) + [{"role": "human", "content": message}]
        if len(calls) == 1:
            conv.append({"role": "ai", "content": "What evaluation criteria would you like?"})
            return {
                "status": "configuring",
                "message": "What evaluation criteria would you like?",
                "conversation": conv,
            }
        conv.append({"role": "ai", "content": "All set! Instance is ready."})
        return {
            "status": "ready",
            "message": "All set! Instance is ready.",
            "conversation": conv,
            "config": OperatorConfig(
                criteria={"originality": 0.5, "feasibility": 0.5},
                guidelines="Focus on AI/ML projects",
            ),
            "threshold": 5,
        }

    return handler


# --- Fixtures ---

@pytest.fixture(autouse=True)
def clear_stores():
    """Reset all in-memory API state before each test."""
    routes._instances.clear()
    routes._submissions.clear()
    routes._results.clear()
    routes._tokens.clear()
    yield


@pytest.fixture
def client():
    from main import app
    return TestClient(app)


# --- Tests ---

def test_operator_init_loop(client):
    """Two-turn init: first response asks for more info, second issues tokens."""
    handler = _make_init_handler()
    with patch.object(skill_card, "init_handler", handler):
        # Turn 1: LLM asks for criteria
        r = client.post("/init", json={
            "skill_name": "hackathon_novelty",
            "message": "I want to run a hackathon",
        })
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "configuring"
        assert body["admin_token"] is None
        assert body["user_token"] is None
        instance_id = body["instance_id"]

        # Turn 2: operator provides criteria → ready
        r = client.post("/init", json={
            "skill_name": "hackathon_novelty",
            "message": "originality 0.5, feasibility 0.5",
            "instance_id": instance_id,
        })
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "ready"
        assert body["admin_token"] is not None
        assert body["user_token"] is not None
        assert body["instance_id"] == instance_id


def test_full_e2e_workflow(client):
    """Full happy path: init → submit below threshold → auto-trigger → view results → manual trigger."""
    handler = _make_init_handler()
    with patch.object(skill_card, "init_handler", handler), \
         patch.object(skill_card, "run", _fake_run_skill):

        # Step 1-2: Operator init loop
        r = client.post("/init", json={
            "skill_name": "hackathon_novelty",
            "message": "setup hackathon",
        })
        instance_id = r.json()["instance_id"]

        r = client.post("/init", json={
            "skill_name": "hackathon_novelty",
            "message": "originality 0.5, feasibility 0.5",
            "instance_id": instance_id,
        })
        admin_token = r.json()["admin_token"]
        user_token = r.json()["user_token"]

        # Step 3: Submit 4 times — all below threshold
        for i in range(1, 5):
            r = client.post(
                "/submit",
                json={"submission_id": f"sub_00{i}", "idea_text": f"Idea number {i}"},
                headers={"X-Instance-Token": user_token},
            )
            assert r.status_code == 200
            body = r.json()
            assert body["status"] == "received_pending"
            assert body["submissions_count"] == i

        # Step 4: 5th submission auto-triggers pipeline
        r = client.post(
            "/submit",
            json={"submission_id": "sub_005", "idea_text": "Fifth idea, triggers pipeline"},
            headers={"X-Instance-Token": user_token},
        )
        assert r.status_code == 200
        assert r.json()["status"] == "received_analysis_complete"

        # Step 5: Participant views their own result
        r = client.get("/results/sub_001", headers={"X-Instance-Token": user_token})
        assert r.status_code == 200
        body = r.json()
        assert body["submission_id"] == "sub_001"
        assert "novelty_score" in body
        assert "criteria_scores" in body

        # Step 6: Operator views all results
        r = client.get("/results", headers={"X-Instance-Token": admin_token})
        assert r.status_code == 200
        results = r.json()["results"]
        assert len(results) == 5
        assert all("submission_id" in res for res in results)

        # Step 7: Operator manual trigger
        r = client.post("/trigger", headers={"X-Instance-Token": admin_token})
        assert r.status_code == 200
        assert r.json()["status"] == "complete"
        assert r.json()["results_count"] == 5


def test_token_enforcement(client):
    """Token-based auth and role enforcement."""
    handler = _make_init_handler()
    with patch.object(skill_card, "init_handler", handler):
        r = client.post("/init", json={"skill_name": "hackathon_novelty", "message": "start"})
        instance_id = r.json()["instance_id"]
        r = client.post("/init", json={
            "skill_name": "hackathon_novelty",
            "message": "criteria ready",
            "instance_id": instance_id,
        })
        admin_token = r.json()["admin_token"]
        user_token = r.json()["user_token"]

    # No token → 401
    r = client.post("/submit", json={"submission_id": "s1", "idea_text": "idea"})
    assert r.status_code == 401

    # Garbage token → 403
    r = client.post(
        "/submit",
        json={"submission_id": "s1", "idea_text": "idea"},
        headers={"X-Instance-Token": "not-a-real-token"},
    )
    assert r.status_code == 403

    # Participant cannot trigger manually
    r = client.post("/trigger", headers={"X-Instance-Token": user_token})
    assert r.status_code == 403

    # Participant cannot view all results
    r = client.get("/results", headers={"X-Instance-Token": user_token})
    assert r.status_code == 403

    # Operator can submit (allowed by role)
    r = client.post(
        "/submit",
        json={"submission_id": "s1", "idea_text": "operator's idea"},
        headers={"X-Instance-Token": admin_token},
    )
    assert r.status_code == 200


def test_result_not_found_before_pipeline(client):
    """Requesting a result before the pipeline runs returns 404."""
    handler = _make_init_handler()
    with patch.object(skill_card, "init_handler", handler):
        r = client.post("/init", json={"skill_name": "hackathon_novelty", "message": "start"})
        instance_id = r.json()["instance_id"]
        r = client.post("/init", json={
            "skill_name": "hackathon_novelty",
            "message": "ready",
            "instance_id": instance_id,
        })
        user_token = r.json()["user_token"]

    r = client.get("/results/sub_001", headers={"X-Instance-Token": user_token})
    assert r.status_code == 404


def test_init_unknown_instance_returns_404(client):
    """Continuing an init conversation with a non-existent instance_id returns 404."""
    r = client.post("/init", json={
        "skill_name": "hackathon_novelty",
        "message": "hello",
        "instance_id": "does-not-exist",
    })
    assert r.status_code == 404


def test_health_endpoint(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert "instances" in body
    assert "hackathon_novelty" in body["skills"]


def test_skills_metadata_endpoints(client):
    # List all skills
    r = client.get("/skills")
    assert r.status_code == 200
    skills = r.json()["skills"]
    assert any(s["name"] == "hackathon_novelty" for s in skills)

    # Single skill
    r = client.get("/skills/hackathon_novelty")
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == "hackathon_novelty"
    assert "input_schema" in body
    assert "trigger_modes" in body
    assert "roles" in body

    # Non-existent skill
    r = client.get("/skills/nonexistent_skill")
    assert r.status_code == 404


def test_init_unknown_skill_returns_404(client):
    """POST /init with a non-existent skill_name returns 404, not 500."""
    r = client.post("/init", json={
        "skill_name": "nonexistent_skill",
        "message": "hello",
    })
    assert r.status_code == 404
    assert "not found" in r.json()["detail"].lower()


def test_init_rejects_empty_criteria():
    """Init handler returns configuring when LLM extracts empty criteria."""
    from skills.hackathon_novelty.init import hackathon_init_handler
    from unittest.mock import patch

    class _FakeLLM:
        def invoke(self, messages):
            class _Resp:
                content = '{"ready": true, "criteria": {}, "guidelines": "", "threshold": 5}'
            return _Resp()

    with patch("skills.hackathon_novelty.init.get_llm", return_value=_FakeLLM()):
        result = hackathon_init_handler("use empty criteria", [])
    assert result["status"] == "configuring"
    assert "empty" in result["message"].lower() or "criterion" in result["message"].lower()


def test_init_rejects_bad_weight_sum():
    """Init handler returns configuring when criteria weights don't sum to ~1.0."""
    from skills.hackathon_novelty.init import hackathon_init_handler
    from unittest.mock import patch

    class _FakeLLM:
        def invoke(self, messages):
            class _Resp:
                content = '{"ready": true, "criteria": {"a": 0.3, "b": 0.3}, "guidelines": "", "threshold": 5}'
            return _Resp()

    with patch("skills.hackathon_novelty.init.get_llm", return_value=_FakeLLM()):
        result = hackathon_init_handler("bad weights", [])
    assert result["status"] == "configuring"
    assert "1.0" in result["message"] or "sum" in result["message"].lower()


def test_init_rejects_non_numeric_threshold():
    """Init handler returns configuring when threshold is non-numeric."""
    from skills.hackathon_novelty.init import hackathon_init_handler
    from unittest.mock import patch

    class _FakeLLM:
        def invoke(self, messages):
            class _Resp:
                content = '{"ready": true, "criteria": {"a": 0.5, "b": 0.5}, "guidelines": "", "threshold": "five"}'
            return _Resp()

    with patch("skills.hackathon_novelty.init.get_llm", return_value=_FakeLLM()):
        result = hackathon_init_handler("bad threshold", [])
    assert result["status"] == "configuring"
    assert "threshold" in result["message"].lower()
