"""
tests/test_simulator.py
Verification tests for Module 7: Synthetic learner simulator.
"""
import time
import math
import numpy as np
import pytest

from hlr.features import RAW_SPEC, SQRT_SPEC
from hlr.predictor import predict_half_life, predict_recall
from ml.simulator import simulate_learners, DEFAULT_LAUNCH_THETA, DEFAULT_TRAINED_THETA

def test_determinism_seed():
    recs1 = simulate_learners(DEFAULT_LAUNCH_THETA, RAW_SPEC, n_students=3, n_concepts=2, n_sessions=4, seed=123)
    recs2 = simulate_learners(DEFAULT_LAUNCH_THETA, RAW_SPEC, n_students=3, n_concepts=2, n_sessions=4, seed=123)
    recs_diff = simulate_learners(DEFAULT_LAUNCH_THETA, RAW_SPEC, n_students=3, n_concepts=2, n_sessions=4, seed=999)

    assert len(recs1) == len(recs2)
    assert len(recs1) > 0
    for r1, r2 in zip(recs1, recs2):
        assert r1.p_observed == r2.p_observed
        assert r1.delta_days == r2.delta_days
        assert r1.x_before == r2.x_before

    # Different seed gives different values
    diff_count = sum(1 for r1, rd in zip(recs1, recs_diff) if r1.p_observed != rd.p_observed or r1.delta_days != rd.delta_days)
    assert diff_count > 0

def test_schema_parity():
    records = simulate_learners(DEFAULT_LAUNCH_THETA, RAW_SPEC, n_students=2, n_concepts=2, n_sessions=3, seed=42)
    assert len(records) > 0
    for r in records:
        assert isinstance(r.student_id, str)
        assert isinstance(r.concept_id, str)
        assert isinstance(r.session_id, str)
        assert 0.0 <= r.p_observed <= 1.0
        assert r.n_answers >= 1
        assert r.delta_days > 0
        assert isinstance(r.counts_before, dict)
        assert "n_right" in r.counts_before
        assert "n_wrong" in r.counts_before
        assert isinstance(r.x_before, list)
        assert len(r.x_before) == 3
        assert r.feature_spec_name == "raw_counts"

def test_label_bounds_and_binary_mode():
    recs_frac = simulate_learners(DEFAULT_LAUNCH_THETA, RAW_SPEC, n_students=2, n_concepts=2, n_sessions=4, questions_per_session=5, label_mode="session_fraction", seed=42)
    for r in recs_frac:
        assert 0.0 <= r.p_observed <= 1.0
        assert r.n_answers == 5

    recs_bin = simulate_learners(DEFAULT_LAUNCH_THETA, RAW_SPEC, n_students=2, n_concepts=2, n_sessions=4, label_mode="binary", seed=42)
    for r in recs_bin:
        assert r.p_observed in (0.0, 1.0)
        assert r.n_answers == 1

def test_exact_mode():
    records = simulate_learners(DEFAULT_LAUNCH_THETA, RAW_SPEC, n_students=3, n_concepts=2, n_sessions=4, exact_mode=True, seed=42)
    for r in records:
        h_true = predict_half_life(DEFAULT_LAUNCH_THETA, r.x_before)
        p_expected = predict_recall(h_true, r.delta_days)
        assert abs(r.p_observed - p_expected) < 1e-9

def test_irregular_intervals_orders_of_magnitude():
    records = simulate_learners(DEFAULT_LAUNCH_THETA, RAW_SPEC, n_students=10, n_concepts=5, n_sessions=15, interval_distribution="lognormal", seed=42)
    deltas = [r.delta_days for r in records]
    ratio = max(deltas) / min(deltas)
    # Span at least three orders of magnitude (ratio >= 1000)
    assert ratio >= 1000.0, f"Expected ratio >= 1000, got {ratio}"

def test_cold_start():
    # Cold start: first session of each concept never produces a training record
    # With 1 session, zero training records should be generated
    records = simulate_learners(DEFAULT_LAUNCH_THETA, RAW_SPEC, n_students=5, n_concepts=3, n_sessions=1, seed=42)
    assert len(records) == 0

def test_extreme_histories_no_overflow():
    # 500 sessions on one concept: h stays inside bounds
    records = simulate_learners(DEFAULT_LAUNCH_THETA, RAW_SPEC, n_students=1, n_concepts=1, n_sessions=500, seed=42)
    assert len(records) > 0
    for r in records:
        h = predict_half_life(DEFAULT_LAUNCH_THETA, r.x_before)
        assert 15.0 / 1440.0 <= h <= 270.0
        assert not math.isnan(h)
        assert not math.isinf(h)

def test_sqrt_feature_spec_vectors():
    records = simulate_learners(DEFAULT_TRAINED_THETA, SQRT_SPEC, n_students=3, n_concepts=2, n_sessions=5, seed=42)
    for r in records:
        assert r.feature_spec_name == "sqrt_counts"
        nr = float(r.counts_before["n_right"])
        nw = float(r.counts_before["n_wrong"])
        assert abs(r.x_before[1] - math.sqrt(nr)) < 1e-7
        assert abs(r.x_before[2] - math.sqrt(nw)) < 1e-7

def test_empirical_calibration():
    # Generate sample with adaptive review intervals around ~0.70
    records = simulate_learners(
        DEFAULT_LAUNCH_THETA,
        RAW_SPEC,
        n_students=60,
        n_concepts=4,
        n_sessions=15,
        questions_per_session=20,
        interval_distribution="adaptive_review",
        seed=42
    )
    p_trues = []
    p_obs = []
    for r in records:
        h = predict_half_life(DEFAULT_LAUNCH_THETA, r.x_before)
        p_t = predict_recall(h, r.delta_days)
        if 0.65 <= p_t <= 0.75:
            p_trues.append(p_t)
            p_obs.append(r.p_observed)

    assert len(p_obs) >= 100
    mean_true = float(np.mean(p_trues))
    mean_obs = float(np.mean(p_obs))
    assert abs(mean_obs - mean_true) < 0.03

def test_generation_speed_50k_records():
    t0 = time.perf_counter()
    records = simulate_learners(
        DEFAULT_LAUNCH_THETA,
        RAW_SPEC,
        n_students=250,
        n_concepts=10,
        n_sessions=25,
        questions_per_session=5,
        seed=42
    )
    elapsed = time.perf_counter() - t0
    assert len(records) >= 50000
    assert elapsed < 30.0, f"50k records took {elapsed:.2f}s, expected < 30s"
