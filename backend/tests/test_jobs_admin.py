"""
backend/tests/test_jobs_admin.py
Verification tests for Module 12: Jobs, Admin API, and Monitoring.
"""
from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient

from main import app
from repositories.memory import InMemoryUnitOfWork
from hlr.config import HLRConfig
from hlr.features import RAW_SPEC, SQRT_SPEC
from ml.model_registry import ModelRegistry, GLOBAL_REGISTRY
from ml.simulator import simulate_learners, DEFAULT_LAUNCH_THETA
from jobs.training_job import run_training_job, acquire_job_lock, JOB_RUNS
from jobs.monitoring_job import run_monitoring_job

client = TestClient(app)

def test_two_workers_same_job_one_executes_other_skips():
    uow = InMemoryUnitOfWork()
    window_key = "2026-10-15-window-concurrent"
    records = simulate_learners(DEFAULT_LAUNCH_THETA, RAW_SPEC, n_students=20, n_concepts=3, n_sessions=6, seed=42)

    # Worker 1 runs job
    run1 = run_training_job(records, window_key=window_key, uow=uow)
    assert run1.status == "completed"

    # Worker 2 attempts same window
    run2 = run_training_job(records, window_key=window_key, uow=uow)
    assert run2.status == "skipped"
    assert "already running or completed" in run2.details["reason"]

def test_insufficient_data_skips_job():
    uow = InMemoryUnitOfWork()
    window_key = "2026-10-15-window-small"
    # Only 5 records (less than 40)
    small_records = simulate_learners(DEFAULT_LAUNCH_THETA, RAW_SPEC, n_students=2, n_concepts=1, n_sessions=3, seed=42)

    run = run_training_job(small_records, window_key=window_key, uow=uow)
    assert run.status == "skipped"
    assert "Insufficient examples" in run.details["reason"]

def test_dirty_data_skips_job():
    uow = InMemoryUnitOfWork()
    window_key = "2026-10-15-window-dirty"
    records = simulate_learners(DEFAULT_LAUNCH_THETA, RAW_SPEC, n_students=20, n_concepts=3, n_sessions=6, seed=42)

    # Corrupt 20% of records with negative delta or NaN
    dirty_records = []
    for idx, r in enumerate(records):
        if idx % 5 == 0:
            dirty_records.append({
                "student_id": r.student_id,
                "p_observed": float("nan"),
                "delta_days": -1.0,
                "x_before": [1.0, 1.0, 0.0]
            })
        else:
            dirty_records.append(r)

    run = run_training_job(dirty_records, window_key=window_key, uow=uow)
    assert run.status == "skipped"
    assert "Dirty data rate" in run.details["reason"]

def test_sufficient_simulated_data_registers_candidate_active_unchanged():
    uow = InMemoryUnitOfWork()
    GLOBAL_REGISTRY.seed_default_model(uow)
    active_before = uow.models.get_active()
    assert active_before is not None

    window_key = "2026-10-15-window-success"
    records = simulate_learners(DEFAULT_LAUNCH_THETA, RAW_SPEC, n_students=25, n_concepts=3, n_sessions=6, seed=42)

    run = run_training_job(records, window_key=window_key, uow=uow)
    assert run.status == "completed"

    cand_id = run.details["candidate_id"]
    cand_model = uow.models.get(cand_id)
    assert cand_model is not None
    assert cand_model.active is False

    # Active model must remain completely unchanged!
    active_after = uow.models.get_active()
    assert active_after.id == active_before.id

def test_monitoring_bound_alert():
    # Seed 50% of concepts at h_max (270.0)
    cfg = HLRConfig()
    states = [
        {"half_life_days": cfg.h_max_days, "p_hat": 0.99} for _ in range(20)
    ] + [
        {"half_life_days": 4.0, "p_hat": 0.70} for _ in range(20)
    ]
    report = run_monitoring_job(states=states, attempts=[], active_model_version="hlr_v0_fixed")
    assert report.share_at_bounds == 0.5
    assert len(report.alerts) > 0
    assert any("saturated at half-life bounds" in a for a in report.alerts)

def test_student_token_on_admin_routes_forbidden_403():
    # Without X-Role: admin, all admin endpoints must return 403
    for path in ["/api/admin/models", "/api/admin/training-runs"]:
        resp_no_header = client.get(path)
        assert resp_no_header.status_code == 403

        resp_student = client.get(path, headers={"X-Role": "student"})
        assert resp_student.status_code == 403

    resp_post = client.post("/api/admin/training-runs/start", headers={"X-Role": "student"})
    assert resp_post.status_code == 403

def test_activate_via_api():
    # With X-Role: admin, promotion gate failure reports reasons
    with client:
        # Get active models
        models_resp = client.get("/api/admin/models", headers={"X-Role": "admin"})
        assert models_resp.status_code == 200

        # Try to activate a model that fails gates
        act_resp = client.post(
            "/api/admin/models/unknown-model/activate",
            headers={"X-Role": "admin"}
        )
        assert act_resp.status_code == 400
        assert "not found" in act_resp.json()["detail"]
