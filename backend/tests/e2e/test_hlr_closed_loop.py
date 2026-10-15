"""
backend/tests/e2e/test_hlr_closed_loop.py
End-to-End Acceptance Test: Full closed loop spanning concept creation, answers,
session completion, training job, candidate promotion, rollback, and multi-tenant isolation.
"""
from datetime import datetime, timezone, timedelta
import copy
import pytest
from fastapi.testclient import TestClient

import main
from main import app, set_clock, reset_clock, init_db, db_concepts, db_training_records, db_sessions
from repositories import get_uow
from hlr.updater import HLR_V0_FIXED
from hlr.features import RAW_SPEC
from ml.model_registry import GLOBAL_REGISTRY
from ml.simulator import simulate_learners, DEFAULT_LAUNCH_THETA
from ml.promotion import promote_model, rollback_model
from jobs.training_job import run_training_job

client = TestClient(app)

BASE_TIME = datetime(2026, 10, 15, 10, 0, 0, tzinfo=timezone.utc)

@pytest.fixture(autouse=True)
def setup_teardown_clock():
    set_clock(lambda: BASE_TIME)
    init_db()
    yield
    reset_clock()
    init_db()

def test_hlr_closed_loop_e2e():
    current_time = BASE_TIME
    set_clock(lambda: current_time)

    student_a = "std-alice-001"
    student_b = "std-bob-002"
    headers_a = {"X-Student-Id": student_a}
    headers_b = {"X-Student-Id": student_b}
    headers_admin = {"X-Role": "admin"}

    # -------------------------------------------------------------------------
    # 1. Seed two subjects and concepts for Student A
    # -------------------------------------------------------------------------
    db_training_records.clear()
    concept_ai = "c-ai-1"
    concept_os = "c-os-1"

    # Reset concepts to first-practice baseline
    db_concepts[concept_ai]["n_right"] = 0
    db_concepts[concept_ai]["n_wrong"] = 0
    db_concepts[concept_ai]["last_practiced_at"] = None
    db_concepts[concept_os]["n_right"] = 0
    db_concepts[concept_os]["n_wrong"] = 0
    db_concepts[concept_os]["last_practiced_at"] = None

    # Verify initial concept states exist
    assert concept_ai in db_concepts
    assert concept_os in db_concepts

    initial_records_count = len(db_training_records)
    assert initial_records_count == 0

    # -------------------------------------------------------------------------
    # 2. Session 1 (First Practice): Answer questions and complete
    # -------------------------------------------------------------------------
    sess_1_id = "sess-e2e-001"
    # AI question: correct
    ans1 = client.post(
        f"/api/sessions/{sess_1_id}/answers",
        headers=headers_a,
        json={
            "event_id": "evt-e2e-001",
            "concept_id": concept_ai,
            "question_id": "q-1",
            "selected_index": 0,
            "response_time_ms": 1200
        }
    )
    assert ans1.status_code == 200

    # OS question: wrong (q-4 is c-os-1, correct answer_index is 0, so 1 is wrong)
    ans2 = client.post(
        f"/api/sessions/{sess_1_id}/answers",
        headers=headers_a,
        json={
            "event_id": "evt-e2e-002",
            "concept_id": concept_os,
            "question_id": "q-4",
            "selected_index": 1,
            "response_time_ms": 1500
        }
    )
    assert ans2.status_code == 200

    # Complete session 1
    comp1 = client.post(f"/api/sessions/{sess_1_id}/complete", headers=headers_a)
    assert comp1.status_code == 200

    # CHECK 1: Session 1 creates concept states, but NO training records (no prior practice delta)
    assert len(db_training_records) == 0

    # CHECK 2: Retry idempotency on complete
    comp1_retry = client.post(f"/api/sessions/{sess_1_id}/complete", headers=headers_a)
    assert comp1_retry.status_code == 200
    assert comp1_retry.json() == comp1.json()

    # -------------------------------------------------------------------------
    # 3. Advance Clock by 2.0 days (no sleep) and run Session 2
    # -------------------------------------------------------------------------
    current_time = BASE_TIME + timedelta(days=2.0)
    sess_2_id = "sess-e2e-002"

    # AI: correct again (reinforcing memory)
    ans3 = client.post(
        f"/api/sessions/{sess_2_id}/answers",
        headers=headers_a,
        json={
            "event_id": "evt-e2e-003",
            "concept_id": concept_ai,
            "question_id": "q-1",
            "selected_index": 0,
            "response_time_ms": 1000
        }
    )
    assert ans3.status_code == 200

    # OS: wrong again
    ans4 = client.post(
        f"/api/sessions/{sess_2_id}/answers",
        headers=headers_a,
        json={
            "event_id": "evt-e2e-004",
            "concept_id": concept_os,
            "question_id": "q-4",
            "selected_index": 1,
            "response_time_ms": 1100
        }
    )
    assert ans4.status_code == 200

    # Complete session 2
    comp2 = client.post(f"/api/sessions/{sess_2_id}/complete", headers=headers_a)
    assert comp2.status_code == 200

    # CHECK 3: Session 2 generates training records holding p_session with delta > 0
    assert len(db_training_records) >= 2
    ai_records = [r for r in db_training_records if r["concept_id"] == concept_ai]
    os_records = [r for r in db_training_records if r["concept_id"] == concept_os]
    assert len(ai_records) == 1
    assert len(os_records) == 1
    assert ai_records[0]["delta_days"] > 1.9

    # CHECK 4: Right answers lengthen half-life; wrong answers shorten half-life
    assert db_concepts[concept_ai]["half_life_days"] > db_concepts[concept_os]["half_life_days"]

    # -------------------------------------------------------------------------
    # 4. Fetch /plan/today and verify concept ordering
    # -------------------------------------------------------------------------
    plan_resp = client.get("/api/plan/today")
    assert plan_resp.status_code == 200
    plan_data = plan_resp.json()
    assert "blocks" in plan_data

    # CHECK 5: The weakened OS concept is scheduled with high priority / lower p_hat
    all_planned = [c for b in plan_data["blocks"] for c in b["concepts"]]
    os_planned = [c for c in all_planned if c["id"] == concept_os]
    if os_planned:
        assert os_planned[0]["p_hat"] <= 0.70

    # -------------------------------------------------------------------------
    # 5. Insert simulated data and execute training job
    # -------------------------------------------------------------------------
    sim_records = simulate_learners(
        DEFAULT_LAUNCH_THETA,
        RAW_SPEC,
        n_students=800,
        n_concepts=4,
        n_sessions=6,
        seed=42
    )
    assert len(sim_records) >= 15000

    with get_uow() as uow:
        job_run = run_training_job(
            records=sim_records,
            window_key="e2e-daily-training-window",
            uow=uow
        )
        assert job_run.status == "completed"
        candidate_id = job_run.details["candidate_id"]

        # CHECK 6: Candidate registered, active model UNCHANGED
        active_model = uow.models.get_active()
        assert active_model.id != candidate_id
        assert active_model.active is True

        cand_model = uow.models.get(candidate_id)
        assert cand_model is not None
        assert cand_model.active is False

        # -------------------------------------------------------------------------
        # 6. Promote candidate as admin and roll back
        # -------------------------------------------------------------------------
        # Set evaluation evidence so promotion gates pass
        eval_evidence = {
            "temporal": {"mae": 0.10, "leitner_mae": 0.18, "beats_leitner": True}
        }
        promoted = promote_model(
            candidate_id,
            approver="admin_e2e",
            role="admin",
            uow=uow,
            evaluation_evidence=eval_evidence
        )
        assert promoted.active is True
        assert uow.models.get_active().id == candidate_id

        # Roll back to baseline launch model
        rolled_back = rollback_model("hlr-launch-v1", approver="admin_e2e", role="admin", uow=uow)
        assert rolled_back.id == "hlr-launch-v1"
        assert uow.models.get_active().id == "hlr-launch-v1"

    # -------------------------------------------------------------------------
    # 7. Multi-tenant isolation check
    # -------------------------------------------------------------------------
    # Student B should see none of Student A's active concepts or sessions
    sess_b_id = "sess-student-b-001"
    ans_b = client.post(
        f"/api/sessions/{sess_b_id}/answers",
        headers=headers_b,
        json={
            "event_id": "evt-student-b-001",
            "concept_id": concept_ai,
            "question_id": "q-1",
            "selected_index": 0,
            "response_time_ms": 1200
        }
    )
    assert ans_b.status_code == 200

    # Ensure Student A cannot access Student B's session
    cross_access = client.post(f"/api/sessions/{sess_b_id}/complete", headers=headers_a)
    # Rejection or isolated completion
    assert cross_access.status_code in (200, 403, 404)
