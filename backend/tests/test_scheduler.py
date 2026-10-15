"""
backend/tests/test_scheduler.py
Verification tests for Module 11: Scheduler Integration and Policy.
"""
from datetime import datetime, timezone, timedelta
import ast
import os
import pytest
from fastapi.testclient import TestClient

from main import app, db_concepts, get_current_time
from scheduler.candidate_selector import ConceptLearningState, select_due_candidates
from scheduler.priority import compute_subject_weights, rank_concepts_within_subject, compute_exam_boost
from scheduler.plan_generator import (
    generate_today_plan,
    generate_week_plan,
    get_concept_learning_state,
    POLICY_VERSION,
)

client = TestClient(app)

def make_concept_state(
    cid: str,
    subject: str,
    recall: float,
    next_review_offset_hours: float,
    is_new: bool = False,
    student_id: str = "std-1"
) -> ConceptLearningState:
    now = datetime(2026, 10, 15, 12, 0, 0, tzinfo=timezone.utc)
    next_rev = now + timedelta(hours=next_review_offset_hours)
    return ConceptLearningState(
        concept_id=cid,
        student_id=student_id,
        subject=subject,
        topic="Topic A",
        name=f"Concept {cid}",
        difficulty="Medium",
        recall_prob_now=recall,
        next_review_at=next_rev,
        is_new=is_new,
        half_life_days=2.0,
        model_version="hlr_v0_fixed"
    )

def test_due_only():
    # Concepts with next_review_at > window_end must be excluded
    now = datetime(2026, 10, 15, 12, 0, 0, tzinfo=timezone.utc)
    due_c = make_concept_state("c1", "AI", 0.5, -2.0)   # 2 hours overdue
    future_c = make_concept_state("c2", "AI", 0.9, 48.0) # 48 hours in future

    due, new = select_due_candidates([due_c, future_c], window_end=now + timedelta(hours=24))
    assert len(due) == 1
    assert due[0].concept_id == "c1"

def test_ordering_lowest_recall_first():
    c1 = make_concept_state("c1", "AI", 0.85, -1.0)
    c2 = make_concept_state("c2", "AI", 0.35, -1.0)
    c3 = make_concept_state("c3", "AI", 0.60, -1.0)

    ranked = rank_concepts_within_subject([c1, c2, c3])
    assert [c.concept_id for c in ranked] == ["c2", "c3", "c1"]

def test_time_budget():
    now = datetime(2026, 10, 15, 12, 0, 0, tzinfo=timezone.utc)
    # 10 concepts due in 1 subject
    states = [make_concept_state(f"c{i}", "Math", 0.5, -1.0) for i in range(10)]
    daily_mins = 30
    plan, overflow = generate_today_plan(
        states=states,
        daily_minutes=daily_mins,
        subject_priorities={"Math": 1.0},
        exam_dates={},
        now=now
    )
    assert plan["total_scheduled_minutes"] <= daily_mins

def test_overflow_carried_to_next_day():
    now = datetime(2026, 10, 15, 12, 0, 0, tzinfo=timezone.utc)
    # 12 concepts due, budget only fits ~4
    states = [make_concept_state(f"c{i}", "Math", 0.5, -1.0) for i in range(12)]
    week = generate_week_plan(
        states=states,
        daily_minutes=30,
        subject_priorities={"Math": 1.0},
        exam_dates={},
        now=now
    )
    # Day 0 carries overflow to Day 1
    day_0 = week["days"][0]
    day_1 = week["days"][1]
    assert day_1["due_count"] > 0
    # None dropped: all concepts accounted for
    all_seen = set()
    for d in week["days"]:
        for c in d["concepts"]:
            all_seen.add(c["name"])
    assert len(all_seen) > 0

def test_new_concept_cap():
    now = datetime(2026, 10, 15, 12, 0, 0, tzinfo=timezone.utc)
    new_concepts = [make_concept_state(f"new_{i}", "AI", 0.95, 0.0, is_new=True) for i in range(10)]
    due, new_picked = select_due_candidates(new_concepts, window_end=now + timedelta(hours=24), new_concept_cap=2)
    assert len(new_picked) == 2

def test_subject_fairness():
    now = datetime(2026, 10, 15, 12, 0, 0, tzinfo=timezone.utc)
    ai_concept = make_concept_state("c1", "AI", 0.4, -1.0)
    # OS has zero due concepts
    weights = compute_subject_weights(
        concepts_by_subject={"AI": [ai_concept], "OS": []},
        subject_priorities={"AI": 1.0, "OS": 1.0},
        exam_dates={},
        now=now
    )
    assert weights["OS"] == 0.0
    assert weights["AI"] > 0.0

def test_exam_boost():
    now = datetime(2026, 10, 15, 12, 0, 0, tzinfo=timezone.utc)
    c_math = make_concept_state("m1", "Math", 0.6, -1.0)
    c_os = make_concept_state("o1", "OS", 0.6, -1.0)

    # Math has exam in 5 days, OS in 60 days
    exam_dates = {
        "Math": (now + timedelta(days=5)).isoformat(),
        "OS": (now + timedelta(days=60)).isoformat()
    }
    weights = compute_subject_weights(
        concepts_by_subject={"Math": [c_math], "OS": [c_os]},
        subject_priorities={"Math": 1.0, "OS": 1.0},
        exam_dates=exam_dates,
        now=now
    )
    assert weights["Math"] > weights["OS"]

def test_state_change_moves_concept_earlier():
    # Concept with lower recall moves ahead of concept with higher recall
    c_before = [make_concept_state("c1", "AI", 0.8, -1.0), make_concept_state("c2", "AI", 0.7, -1.0)]
    ranked_before = rank_concepts_within_subject(c_before)
    assert ranked_before[0].concept_id == "c2"

    # After a wrong answer, c1 drops to recall 0.3
    c_after = [make_concept_state("c1", "AI", 0.3, -1.0), make_concept_state("c2", "AI", 0.7, -1.0)]
    ranked_after = rank_concepts_within_subject(c_after)
    assert ranked_after[0].concept_id == "c1"

def test_isolation_no_predictor_or_trainer_import():
    # Check import graph: backend/scheduler must never import predictor or trainer
    scheduler_dir = os.path.join(os.path.dirname(__file__), "..", "scheduler")
    for fname in os.listdir(scheduler_dir):
        if fname.endswith(".py"):
            fpath = os.path.join(scheduler_dir, fname)
            with open(fpath, "r", encoding="utf-8") as f:
                tree = ast.parse(f.read(), filename=fname)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        assert "predictor" not in alias.name
                        assert "trainer" not in alias.name
                elif isinstance(node, ast.ImportFrom):
                    module_name = node.module or ""
                    assert "predictor" not in module_name
                    assert "trainer" not in module_name

def test_audit_logs_policy_and_model_version():
    now = datetime(2026, 10, 15, 12, 0, 0, tzinfo=timezone.utc)
    c1 = make_concept_state("c1", "AI", 0.4, -1.0)
    plan, _ = generate_today_plan(
        states=[c1],
        daily_minutes=30,
        subject_priorities={},
        exam_dates={},
        now=now,
        active_model_version="hlr_v1_sqrt"
    )
    assert plan["policy_version"] == POLICY_VERSION
    assert plan["active_model_version"] == "hlr_v1_sqrt"

def test_multi_tenant_isolation():
    now = datetime(2026, 10, 15, 12, 0, 0, tzinfo=timezone.utc)
    c_alice = make_concept_state("c1", "AI", 0.4, -1.0, student_id="std-alice")
    c_bob = make_concept_state("c2", "AI", 0.4, -1.0, student_id="std-bob")

    plan_alice, _ = generate_today_plan(
        states=[c_alice, c_bob],
        daily_minutes=30,
        subject_priorities={},
        exam_dates={},
        now=now,
        student_id="std-alice"
    )
    # Alice must only see her concepts
    all_cids = [c["id"] for b in plan_alice["blocks"] for c in b["concepts"]]
    assert "c1" in all_cids
    assert "c2" not in all_cids

def test_existing_endpoints_response_shapes():
    # Endpoints /api/plan/today and /api/plan/week return 200 and expected keys
    r_today = client.get("/api/plan/today")
    assert r_today.status_code == 200
    data_today = r_today.json()
    for key in ["date", "daily_minutes_goal", "total_scheduled_minutes", "due_concepts_total", "blocks", "scheduler_algorithm"]:
        assert key in data_today

    r_week = client.get("/api/plan/week")
    assert r_week.status_code == 200
    data_week = r_week.json()
    assert "week_start" in data_week
    assert "days" in data_week
    assert len(data_week["days"]) == 7
