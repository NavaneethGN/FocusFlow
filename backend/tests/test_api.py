import pytest
from fastapi.testclient import TestClient
from main import app, seed_initial_data
from app.core.database import Base, engine, SessionLocal
from app.models.models import ConceptState, TrainingRecord, Attempt


@pytest.fixture(scope="module")
def client():
    Base.metadata.create_all(bind=engine)
    seed_initial_data()
    with TestClient(app) as test_client:
        yield test_client


def test_health_endpoint(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_get_concepts(client):
    response = client.get("/api/concepts")
    assert response.status_code == 200
    concepts = response.json()
    assert len(concepts) >= 3
    first = concepts[0]
    assert "name" in first
    assert "h_hat" in first
    assert "p_hat_current" in first


def test_concept_curve(client):
    response = client.get("/api/concepts/1/curve")
    assert response.status_code == 200
    data = response.json()
    assert data["concept_id"] == 1
    assert "curve_points" in data
    assert len(data["curve_points"]) > 10
    # Day 0 should start high
    assert data["curve_points"][0]["probability"] >= 0.95


def test_quiz_session_lifecycle(client):
    """Complete integration test:
    1. Start quiz session
    2. Submit answers (with idempotency verification)
    3. Complete session and verify HLR state updates & training records
    """
    # 1. Start quiz
    start_res = client.post("/api/quizzes/start", json={"user_id": 1, "limit": 3})
    assert start_res.status_code == 200
    quiz_data = start_res.json()
    session_id = quiz_data["session_id"]
    questions = quiz_data["questions"]
    assert len(questions) > 0

    first_q = questions[0]
    event_id = f"test-event-{session_id}-{first_q['question_id']}"

    # 2. Submit answer
    answer_res = client.post(
        f"/api/sessions/{session_id}/answers",
        json={
            "event_id": event_id,
            "question_id": first_q["question_id"],
            "selected_index": 0,
        },
    )
    assert answer_res.status_code == 200
    ans_data = answer_res.json()
    assert ans_data["already_recorded"] is False

    # 3. Test idempotency: re-submit same event_id
    duplicate_res = client.post(
        f"/api/sessions/{session_id}/answers",
        json={
            "event_id": event_id,
            "question_id": first_q["question_id"],
            "selected_index": 0,
        },
    )
    assert duplicate_res.status_code == 200
    dup_data = duplicate_res.json()
    assert dup_data["already_recorded"] is True

    # 4. Complete session
    complete_res = client.post(f"/api/sessions/{session_id}/complete")
    assert complete_res.status_code == 200
    comp_data = complete_res.json()
    assert comp_data["session_id"] == session_id
    assert comp_data["total_attempts"] >= 1
    assert len(comp_data["concepts_updated"]) >= 1

    # Verify that a training record was saved
    db = SessionLocal()
    try:
        tr = db.query(TrainingRecord).filter(TrainingRecord.session_id == session_id).first()
        assert tr is not None
        assert tr.p >= 0.0
        assert tr.x_before is not None
    finally:
        db.close()


def test_dashboard_endpoint(client):
    response = client.get("/api/dashboard?user_id=1")
    assert response.status_code == 200
    data = response.json()
    assert "overall_retention" in data
    assert "subjects" in data
    assert len(data["subjects"]) >= 1


def test_study_plan_endpoints(client):
    today_res = client.get("/api/plan/today?user_id=1")
    assert today_res.status_code == 200
    today_data = today_res.json()
    assert len(today_data["plan"]) == 1
    assert "concepts" in today_data["plan"][0]

    week_res = client.get("/api/plan/week?user_id=1")
    assert week_res.status_code == 200
    week_data = week_res.json()
    assert len(week_data["plan"]) == 7


def test_materials_upload(client):
    notes = """
    Cache Coherence: Protocols to ensure consistency among multiple local caches.
    Write-Through: Data is written to cache and main memory simultaneously.
    Write-Back: Data is written only to cache; memory is updated only on replacement.
    """
    response = client.post(
        "/api/materials",
        json={
            "subject_id": 1,
            "title": "Cache Architecture",
            "content": notes,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["concepts_generated"] >= 1
    assert data["questions_generated"] >= 1


def test_settings_endpoints(client):
    get_res = client.get("/api/settings?user_id=1")
    assert get_res.status_code == 200
    assert "daily_minutes" in get_res.json()

    put_res = client.put(
        "/api/settings?user_id=1",
        json={
            "daily_minutes": 90,
            "subject_priorities": {"1": 1.5},
            "exam_dates": {"1": "2026-12-01"},
        },
    )
    assert put_res.status_code == 200
    assert put_res.json()["daily_minutes"] == 90
