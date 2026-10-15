"""
tests/test_answers_api.py
Verification tests for Module 5: Answer ingestion (idempotent, server-scored).
"""
import concurrent.futures
from datetime import datetime, timezone, timedelta
import pytest
from fastapi.testclient import TestClient

import main

client = TestClient(main.app)

@pytest.fixture(autouse=True)
def reset_db_state():
    main.init_db()
    yield
    main.init_db()

def test_missing_student_identity_returns_401():
    resp = client.post("/api/sessions/sess-1/answers", json={
        "event_id": "evt-no-auth",
        "concept_id": "c-ai-1",
        "question_id": "q-1",
        "is_correct": True,
        "selected_index": 0
    })
    assert resp.status_code == 401

def test_valid_answer_server_scored():
    # q-1 answer_index is 0
    resp = client.post(
        "/api/sessions/sess-1/answers",
        headers={"X-Student-Id": "std-1"},
        json={
            "event_id": "evt-valid-1",
            "concept_id": "c-ai-1",
            "question_id": "q-1",
            "is_correct": False,  # Client lies
            "selected_index": 0,   # Correct answer
            "response_time_ms": 1200
        }
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["recorded"] is True
    assert data["is_correct"] is True  # Computed by server!

def test_client_sends_correct_for_wrong_choice_ignored():
    # q-1 answer_index is 0. Selected index 1 is WRONG.
    resp = client.post(
        "/api/sessions/sess-1/answers",
        headers={"X-Student-Id": "std-1"},
        json={
            "event_id": "evt-cheat-1",
            "concept_id": "c-ai-1",
            "question_id": "q-1",
            "is_correct": True,  # Client lies
            "selected_index": 1,  # WRONG
            "response_time_ms": 1200
        }
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_correct"] is False  # Server override!

def test_idempotent_duplicate_event_id_sent_5_times():
    payload = {
        "event_id": "evt-repeat-1",
        "concept_id": "c-ai-1",
        "question_id": "q-1",
        "is_correct": True,
        "selected_index": 0,
        "response_time_ms": 1200
    }
    initial_count = len(main.db_attempts)
    first_resp = client.post(
        "/api/sessions/sess-repeat/answers",
        headers={"X-Student-Id": "std-1"},
        json=payload
    )
    assert first_resp.status_code == 200

    for _ in range(4):
        r = client.post(
            "/api/sessions/sess-repeat/answers",
            headers={"X-Student-Id": "std-1"},
            json=payload
        )
        assert r.status_code == 200
        assert r.json() == first_resp.json()

    # Exactly one row was added to db_attempts
    matching = [a for a in main.db_attempts if a["event_id"] == "evt-repeat-1"]
    assert len(matching) == 1

def test_another_student_session_rejected():
    # Student 1 creates session
    client.post(
        "/api/sessions/sess-multi-user/answers",
        headers={"X-Student-Id": "std-1"},
        json={
            "event_id": "evt-std1",
            "concept_id": "c-ai-1",
            "question_id": "q-1",
            "is_correct": True,
            "selected_index": 0
        }
    )
    # Student 2 tries to submit to student 1's session
    resp = client.post(
        "/api/sessions/sess-multi-user/answers",
        headers={"X-Student-Id": "std-2"},
        json={
            "event_id": "evt-std2",
            "concept_id": "c-ai-1",
            "question_id": "q-1",
            "is_correct": True,
            "selected_index": 0
        }
    )
    assert resp.status_code in (403, 404)

def test_completed_session_returns_409():
    # Complete session
    main.db_sessions["sess-done"] = {
        "id": "sess-done",
        "student_id": "std-1",
        "status": "completed",
        "attempts": []
    }
    resp = client.post(
        "/api/sessions/sess-done/answers",
        headers={"X-Student-Id": "std-1"},
        json={
            "event_id": "evt-late",
            "concept_id": "c-ai-1",
            "question_id": "q-1",
            "is_correct": True,
            "selected_index": 0
        }
    )
    assert resp.status_code == 409

def test_draft_or_flagged_question_returns_422():
    # Add draft question
    main.db_questions.append({
        "id": "q-draft-test",
        "concept_id": "c-ai-1",
        "concept_name": "Test",
        "subject": "Artificial Intelligence",
        "text": "Draft Q",
        "options": ["A", "B"],
        "answer_index": 0,
        "explanation": "Exp",
        "status": "draft"
    })
    resp = client.post(
        "/api/sessions/sess-draft/answers",
        headers={"X-Student-Id": "std-1"},
        json={
            "event_id": "evt-draft",
            "concept_id": "c-ai-1",
            "question_id": "q-draft-test",
            "is_correct": True,
            "selected_index": 0
        }
    )
    assert resp.status_code == 422

def test_future_timestamp_returns_422():
    future_time = (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat()
    resp = client.post(
        "/api/sessions/sess-time/answers",
        headers={"X-Student-Id": "std-1"},
        json={
            "event_id": "evt-future",
            "concept_id": "c-ai-1",
            "question_id": "q-1",
            "is_correct": True,
            "selected_index": 0,
            "answered_at": future_time
        }
    )
    assert resp.status_code == 422

def test_concurrent_duplicate_event_id():
    event_id = "evt-concurrent-100"
    payload = {
        "event_id": event_id,
        "concept_id": "c-ai-1",
        "question_id": "q-1",
        "is_correct": True,
        "selected_index": 0
    }

    def send_req():
        return client.post(
            "/api/sessions/sess-conc/answers",
            headers={"X-Student-Id": "std-conc"},
            json=payload
        )

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(send_req) for _ in range(20)]
        results = [f.result() for f in futures]

    assert all(r.status_code == 200 for r in results)
    matching = [a for a in main.db_attempts if a["event_id"] == event_id]
    assert len(matching) == 1
