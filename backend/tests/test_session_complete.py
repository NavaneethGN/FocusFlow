"""
tests/test_session_complete.py
Verification tests for Module 6: Session completion pipeline.
"""
import concurrent.futures
from datetime import datetime, timezone, timedelta
import math
import pytest
from fastapi.testclient import TestClient

from hlr.features import ConceptCounts, SQRT_SPEC
from hlr.updater import ModelArtifact, HLR_V0_FIXED
from learning.session_aggregator import aggregate_session_attempts
from learning.training_record_builder import build_training_record
import main

client = TestClient(main.app)

@pytest.fixture(autouse=True)
def reset_db_state():
    main.init_db()
    yield
    main.init_db()

def test_session_recall_aggregation():
    # BFS 3 of 4, DFS 1 of 2, Trees 0 of 3
    attempts = [
        {"event_id": "e1", "concept_id": "c-bfs", "is_correct": True},
        {"event_id": "e2", "concept_id": "c-bfs", "is_correct": True},
        {"event_id": "e3", "concept_id": "c-bfs", "is_correct": True},
        {"event_id": "e4", "concept_id": "c-bfs", "is_correct": False},
        {"event_id": "e5", "concept_id": "c-dfs", "is_correct": True},
        {"event_id": "e6", "concept_id": "c-dfs", "is_correct": False},
        {"event_id": "e7", "concept_id": "c-trees", "is_correct": False},
        {"event_id": "e8", "concept_id": "c-trees", "is_correct": False},
        {"event_id": "e9", "concept_id": "c-trees", "is_correct": False},
    ]
    stats = aggregate_session_attempts(attempts)
    assert stats["c-bfs"].p_session == 0.75
    assert stats["c-dfs"].p_session == 0.50
    assert stats["c-trees"].p_session == 0.00

def test_x_before_correctness_and_no_future_leakage():
    # Prior 3 right, 1 wrong; sqrt spec; session adds 2 right, 1 wrong
    model_sqrt = ModelArtifact(
        name="hlr_sqrt_test",
        theta=[0.0, 1.0, -1.0],
        feature_spec=SQRT_SPEC
    )
    counts_before = ConceptCounts(3, 1)
    stats = aggregate_session_attempts([
        {"event_id": "ev1", "concept_id": "c-1", "is_correct": True},
        {"event_id": "ev2", "concept_id": "c-1", "is_correct": True},
        {"event_id": "ev3", "concept_id": "c-1", "is_correct": False},
    ])
    t0 = datetime(2026, 10, 10, 12, 0, 0, tzinfo=timezone.utc)
    t1 = datetime(2026, 10, 15, 12, 0, 0, tzinfo=timezone.utc)

    rec = build_training_record(
        student_id="std-1",
        concept_id="c-1",
        session_id="sess-1",
        stats=stats["c-1"],
        counts_before=counts_before,
        last_practiced_at=t0,
        completed_at=t1,
        model=model_sqrt
    )
    # x_before: [1.0, sqrt(3), sqrt(1)]
    assert rec.x_before[0] == 1.0
    assert abs(rec.x_before[1] - math.sqrt(3.0)) < 1e-9
    assert rec.x_before[2] == 1.0

    # Counts after: 5 right, 2 wrong. x_after would be [1.0, sqrt(5), sqrt(2)].
    # Prove x_before != x_after (no future leakage!)
    assert rec.x_before[1] != math.sqrt(5.0)

def test_first_practice_creates_state_no_training_record():
    # Seed new concept with 0 right, 0 wrong
    main.db_concepts["c-new"] = {
        "id": "c-new",
        "name": "New Concept",
        "subject": "Artificial Intelligence",
        "difficulty": "Medium",
        "n_right": 0,
        "n_wrong": 0,
        "last_practiced_at": None,
        "half_life_days": 1.0,
        "p_hat": 0.99,
        "next_review_at": datetime.now(timezone.utc).isoformat(),
        "is_due": True
    }
    main.db_sessions["sess-first"] = {
        "id": "sess-first",
        "student_id": "std-1",
        "status": "open",
        "attempts": [
            {"event_id": "e-new-1", "concept_id": "c-new", "is_correct": True}
        ]
    }
    records_count_before = len(main.db_training_records)
    resp = client.post("/api/sessions/sess-first/complete")
    assert resp.status_code == 200
    # First practice must NOT produce a training record (no delta)
    assert len(main.db_training_records) == records_count_before
    # But state was updated: 1 right, 0 wrong
    assert main.db_concepts["c-new"]["n_right"] == 1

def test_second_practice_produces_training_record_with_p_session():
    # Setup c-new
    main.db_concepts["c-new"] = {
        "id": "c-new",
        "name": "New Concept",
        "subject": "Artificial Intelligence",
        "difficulty": "Medium",
        "n_right": 0,
        "n_wrong": 0,
        "last_practiced_at": None,
        "half_life_days": 1.0,
        "p_hat": 0.99,
        "next_review_at": datetime.now(timezone.utc).isoformat(),
        "is_due": True
    }
    # Session 1: first practice
    main.db_sessions["sess-first-init"] = {
        "id": "sess-first-init",
        "student_id": "std-1",
        "status": "open",
        "attempts": [
            {"event_id": "e-new-1", "concept_id": "c-new", "is_correct": True}
        ]
    }
    client.post("/api/sessions/sess-first-init/complete")
    assert main.db_concepts["c-new"]["n_right"] == 1

    # Session 2: second practice on c-new
    main.db_sessions["sess-second"] = {
        "id": "sess-second",
        "student_id": "std-1",
        "status": "open",
        "attempts": [
            {"event_id": "e-new-2", "concept_id": "c-new", "is_correct": True},
            {"event_id": "e-new-3", "concept_id": "c-new", "is_correct": False}
        ]
    }
    records_before = len(main.db_training_records)
    resp = client.post("/api/sessions/sess-second/complete")
    assert resp.status_code == 200

    # Exactly one training record was created!
    assert len(main.db_training_records) == records_before + 1
    new_rec = main.db_training_records[-1]
    assert new_rec["concept_id"] == "c-new"
    assert new_rec["p_observed"] == 0.5  # 1 of 2 correct
    assert new_rec["n_answers"] == 2
    assert new_rec["delta_days"] > 0
    assert new_rec["counts_before"]["n_right"] == 1
    assert new_rec["counts_before"]["n_wrong"] == 0

def test_retry_safety_calling_complete_twice():
    main.db_sessions["sess-retry"] = {
        "id": "sess-retry",
        "student_id": "std-1",
        "status": "open",
        "attempts": [
            {"event_id": "e-r-1", "concept_id": "c-ai-1", "is_correct": True}
        ]
    }
    resp1 = client.post("/api/sessions/sess-retry/complete")
    assert resp1.status_code == 200
    data1 = resp1.json()

    records_count = len(main.db_training_records)
    c_right = main.db_concepts["c-ai-1"]["n_right"]

    resp2 = client.post("/api/sessions/sess-retry/complete")
    assert resp2.status_code == 200
    assert resp2.json() == data1
    assert len(main.db_training_records) == records_count
    assert main.db_concepts["c-ai-1"]["n_right"] == c_right

def test_concurrent_completes_idempotent():
    main.db_sessions["sess-conc-comp"] = {
        "id": "sess-conc-comp",
        "student_id": "std-1",
        "status": "open",
        "attempts": [
            {"event_id": "e-c-1", "concept_id": "c-ai-1", "is_correct": True}
        ]
    }
    c_right_initial = main.db_concepts["c-ai-1"]["n_right"]

    def do_complete():
        return client.post("/api/sessions/sess-conc-comp/complete")

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as ex:
        futures = [ex.submit(do_complete) for _ in range(10)]
        results = [f.result() for f in futures]

    assert all(r.status_code == 200 for r in results)
    # n_right should have incremented exactly once
    assert main.db_concepts["c-ai-1"]["n_right"] == c_right_initial + 1

def test_replayed_events_deduplicated():
    # If the same event_id is replayed 3 times in the session attempts, it must only count once
    main.db_sessions["sess-replayed"] = {
        "id": "sess-replayed",
        "student_id": "std-1",
        "status": "open",
        "attempts": [
            {"event_id": "ev-same", "concept_id": "c-ai-1", "is_correct": True},
            {"event_id": "ev-same", "concept_id": "c-ai-1", "is_correct": True},
            {"event_id": "ev-same", "concept_id": "c-ai-1", "is_correct": True},
        ]
    }
    c_right_initial = main.db_concepts["c-ai-1"]["n_right"]
    resp = client.post("/api/sessions/sess-replayed/complete")
    assert resp.status_code == 200
    # Must increment by 1, not 3!
    assert main.db_concepts["c-ai-1"]["n_right"] == c_right_initial + 1
