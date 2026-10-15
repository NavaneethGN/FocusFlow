"""
backend/tests/test_evaluation.py
Verification tests for Module 9: Evaluation metrics, baselines, and leakage-safe splits.
"""
from datetime import datetime, timezone, timedelta
import math
import numpy as np
import pytest

from hlr.config import HLRConfig
from hlr.features import RAW_SPEC, SQRT_SPEC
from hlr.predictor import HLRValidationError
from hlr.updater import ModelArtifact, HLR_V0_FIXED
from hlr.evaluation import (
    compute_mae,
    compute_rmse,
    compute_auc,
    compute_brier_score,
    compute_calibration_table,
    evaluate_models,
)
from ml.dataset_builder import (
    build_dataset_snapshot,
    temporal_split,
    student_holdout_split,
)
from ml.simulator import simulate_learners, DEFAULT_LAUNCH_THETA

def test_perfect_predictions():
    y = [0.2, 0.5, 0.9, 0.1]
    assert compute_mae(y, y) == 0.0
    assert compute_rmse(y, y) == 0.0

def test_small_hand_computed_set():
    y_true = [0.8, 0.2]
    y_pred = [0.5, 0.6]
    # Errors: |0.8 - 0.5| = 0.3, |0.2 - 0.6| = 0.4 -> MAE = 0.35
    # Squared: 0.09 + 0.16 = 0.25 -> MSE = 0.125 -> RMSE = sqrt(0.125)
    assert abs(compute_mae(y_true, y_pred) - 0.35) < 1e-9
    assert abs(compute_rmse(y_true, y_pred) - math.sqrt(0.125)) < 1e-9

def test_binary_only_metrics():
    # Fractions must be refused for AUC and Brier
    frac_labels = [0.25, 0.75, 1.0]
    preds = [0.3, 0.7, 0.9]
    with pytest.raises(HLRValidationError):
        compute_auc(frac_labels, preds)
    with pytest.raises(HLRValidationError):
        compute_brier_score(frac_labels, preds)

    # Pure binary labels succeed
    bin_labels = [0.0, 1.0, 1.0, 0.0]
    auc = compute_auc(bin_labels, preds + [0.1])
    brier = compute_brier_score(bin_labels, preds + [0.1])
    assert 0.0 <= auc <= 1.0
    assert 0.0 <= brier <= 1.0

def test_temporal_split():
    base = datetime(2026, 3, 1, 10, 0, 0, tzinfo=timezone.utc)
    recs = [
        {"session_id": "s1", "student_id": "u1", "created_at": base + timedelta(hours=1)},
        {"session_id": "s2", "student_id": "u1", "created_at": base + timedelta(hours=3)},
        {"session_id": "s3", "student_id": "u2", "created_at": base + timedelta(hours=5)},
    ]
    cutoff = base + timedelta(hours=2)
    train, test = temporal_split(recs, cutoff)

    assert len(train) == 1
    assert len(test) == 2
    max_train_time = max(r["created_at"] for r in train)
    min_test_time = min(r["created_at"] for r in test)
    assert min_test_time > max_train_time

def test_student_holdout_split():
    records = simulate_learners(DEFAULT_LAUNCH_THETA, RAW_SPEC, n_students=20, n_concepts=2, n_sessions=4, seed=42)
    train, test = student_holdout_split(records, holdout_fraction=0.25, seed=42)

    train_students = set(r.student_id for r in train)
    test_students = set(r.student_id for r in test)

    # Zero student overlap guarantee
    assert len(train_students.intersection(test_students)) == 0
    assert len(train) + len(test) == len(records)
    assert len(test_students) == 5

def test_group_integrity():
    # Ensure no student-concept-session is fragmented across sets
    records = simulate_learners(DEFAULT_LAUNCH_THETA, RAW_SPEC, n_students=10, n_concepts=3, n_sessions=4, seed=42)
    cutoff = datetime(2026, 1, 4, 0, 0, 0, tzinfo=timezone.utc)
    train, test = temporal_split(records, cutoff)

    train_sessions = set(r.session_id for r in train)
    test_sessions = set(r.session_id for r in test)
    assert len(train_sessions.intersection(test_sessions)) == 0

def test_snapshot_immutability():
    records = simulate_learners(DEFAULT_LAUNCH_THETA, RAW_SPEC, n_students=10, n_concepts=2, n_sessions=3, seed=42)
    snap1 = build_dataset_snapshot(records, {"min_delta_days": 0.1})
    snap2 = build_dataset_snapshot(records, {"min_delta_days": 0.1})
    assert snap1.row_hash == snap2.row_hash
    assert snap1.snapshot_id == snap2.snapshot_id

    # Changed data yields new hash
    modified_records = list(records)[:-1]
    snap3 = build_dataset_snapshot(modified_records, {"min_delta_days": 0.1})
    assert snap3.row_hash != snap1.row_hash

def test_same_example_guarantee_and_baselines():
    truth = [0.15, 1.42, -1.18]
    records = simulate_learners(truth, SQRT_SPEC, n_students=50, n_concepts=3, n_sessions=8, exact_mode=True, seed=42)
    
    true_model = ModelArtifact("truth_model", truth, SQRT_SPEC, HLRConfig())
    report = evaluate_models({"true_model": true_model}, records)

    assert report.n_examples == len(records)
    # Check that both candidate and all baselines scored the same number of examples
    assert report.models["true_model"].n_examples == len(records)
    assert report.baselines["hlr_v0_fixed"].n_examples == len(records)
    assert report.baselines["constant_mean"].n_examples == len(records)
    assert report.baselines["historical_accuracy"].n_examples == len(records)

    # True model should beat constant mean and Leitner baseline on simulated ground truth
    m_mae = report.models["true_model"].metrics["mae"].value
    c_mae = report.baselines["constant_mean"].metrics["mae"].value
    l_mae = report.baselines["hlr_v0_fixed"].metrics["mae"].value
    h_mae = report.baselines["historical_accuracy"].metrics["mae"].value

    assert m_mae < c_mae
    assert m_mae < l_mae
    assert m_mae < h_mae

def test_calibration_on_true_theta():
    truth = [0.0, 1.0, -1.0]
    records = simulate_learners(truth, RAW_SPEC, n_students=200, n_concepts=4, n_sessions=6, exact_mode=True, seed=42)
    true_model = ModelArtifact("truth_model", truth, RAW_SPEC, HLRConfig())
    report = evaluate_models({"truth_model": true_model}, records)

    cal_table = report.models["truth_model"].calibration_table
    for b in cal_table:
        if b.count >= 20:
            # On exact simulated data, bin mean should be within 0.05 of predicted
            assert b.calibration_error < 0.05, f"Bin {b.bin_index} cal error {b.calibration_error} exceeds 0.05"

def test_bootstrap_ci_narrows_with_more_data():
    truth = [0.0, 1.0, -1.0]
    small_records = simulate_learners(truth, RAW_SPEC, n_students=20, n_concepts=2, n_sessions=4, exact_mode=False, seed=42)
    large_records = simulate_learners(truth, RAW_SPEC, n_students=120, n_concepts=2, n_sessions=4, exact_mode=False, seed=42)

    model = ModelArtifact("truth_model", truth, RAW_SPEC, HLRConfig())
    rep_small = evaluate_models({"model": model}, small_records, n_bootstraps=100)
    rep_large = evaluate_models({"model": model}, large_records, n_bootstraps=100)

    ci_small = rep_small.models["model"].metrics["mae"]
    ci_large = rep_large.models["model"].metrics["mae"]

    width_small = ci_small.ci_95_upper - ci_small.ci_95_lower
    width_large = ci_large.ci_95_upper - ci_large.ci_95_lower
    assert width_small > 0.0
    assert width_large < width_small
