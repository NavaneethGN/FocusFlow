"""
tests/test_updater.py
Verification tests for Module 3: Model artifact, updater, and Leitner-equivalent fixed model.
"""
from datetime import datetime, timezone, timedelta
import pytest

from hlr.config import HLRConfig
from hlr.features import ConceptCounts, RAW_SPEC, SQRT_SPEC
from hlr.predictor import HLRValidationError
from hlr.updater import (
    ModelArtifact,
    HLR_V0_FIXED,
    LAUNCH_THETA,
    apply_outcome,
    compute_state,
)
from tests import legacy_reference

def test_model_construction_validation():
    # Length 2 theta with 3-feature spec should raise HLRValidationError
    with pytest.raises(HLRValidationError):
        ModelArtifact(name="invalid", theta=[1.0, 2.0], feature_spec=RAW_SPEC)

def test_new_concept_default():
    counts = ConceptCounts(0, 0)
    now = datetime(2026, 10, 15, 12, 0, 0, tzinfo=timezone.utc)
    state = compute_state(counts, HLR_V0_FIXED, None, now)
    assert state.half_life_days == 1.0  # 2^0 = 1
    assert state.recall_now is None
    assert state.next_review_at == now
    assert state.is_new is True

def test_review_example():
    counts = ConceptCounts(5, 3)
    now = datetime(2026, 10, 15, 12, 0, 0, tzinfo=timezone.utc)
    last = now - timedelta(days=2.0)
    state = compute_state(counts, HLR_V0_FIXED, last, now)
    assert state.half_life_days == 4.0  # 2^(0 + 5 - 3) = 2^2 = 4.0
    assert state.is_new is False

def test_wrong_shortens():
    counts = ConceptCounts(0, 2)
    now = datetime(2026, 10, 15, 12, 0, 0, tzinfo=timezone.utc)
    last = now - timedelta(days=1.0)
    state = compute_state(counts, HLR_V0_FIXED, last, now)
    assert state.half_life_days == 0.25  # 2^(0 - 2) = 0.25

def test_legacy_parity_grid():
    """Verify compute_state half-life equals legacy for all 961 pairs (0 to 30)."""
    now = datetime(2026, 10, 15, 12, 0, 0, tzinfo=timezone.utc)
    for nr in range(31):
        for nw in range(31):
            counts = ConceptCounts(nr, nw)
            state = compute_state(counts, HLR_V0_FIXED, now, now)
            x_leg = [1.0, float(nr), float(nw)]
            h_leg = legacy_reference.half_life(LAUNCH_THETA, x_leg)
            assert abs(state.half_life_days - h_leg) <= 1e-12

def test_monotonic_learning():
    now = datetime(2026, 10, 15, 12, 0, 0, tzinfo=timezone.utc)
    for nr in range(0, 5):
        for nw in range(0, 5):
            c1 = ConceptCounts(nr, nw)
            c2 = apply_outcome(c1, 1, 0)
            s1 = compute_state(c1, HLR_V0_FIXED, now, now)
            s2 = compute_state(c2, HLR_V0_FIXED, now, now)
            assert s2.half_life_days == min(s1.half_life_days * 2.0, 270.0)

def test_immutability_apply_outcome():
    c_orig = ConceptCounts(2, 1)
    c_new = apply_outcome(c_orig, 3, 2)
    assert c_new.n_right == 5
    assert c_new.n_wrong == 3
    assert c_orig.n_right == 2
    assert c_orig.n_wrong == 1

def test_recall_now_and_overdue():
    t0 = datetime(2026, 10, 10, 12, 0, 0, tzinfo=timezone.utc)
    t_after_4_days = t0 + timedelta(days=4.0)
    counts = ConceptCounts(5, 3)  # h = 4.0 days
    state = compute_state(counts, HLR_V0_FIXED, t0, t_after_4_days)
    assert abs(state.recall_now - 0.5) < 1e-9

    # Next review at 0.70 is ~2.058 days after t0.
    # At t0 + 4 days, concept is overdue and recall is 0.5 < 0.70.
    assert t_after_4_days > state.next_review_at
    assert state.recall_now < 0.70

def test_naive_datetime_in_compute_state_rejected():
    naive = datetime(2026, 10, 15, 12, 0, 0)
    counts = ConceptCounts(3, 1)
    with pytest.raises(HLRValidationError):
        compute_state(counts, HLR_V0_FIXED, None, naive)

def test_scripted_hand_computed_scenario(capsys):
    """Scripted example: 5 right, 3 wrong, then 5 idle days."""
    last_practice = datetime(2026, 10, 1, 12, 0, 0, tzinfo=timezone.utc)
    now = last_practice + timedelta(days=5.0)
    counts = ConceptCounts(5, 3)
    state = compute_state(counts, HLR_V0_FIXED, last_practice, now, threshold=0.70)

    # By hand:
    # theta = [0, 1, -1], x = [1, 5, 3] -> dot = 0 + 5 - 3 = 2 -> h = 2^2 = 4.0 days
    # delta = 5.0 days -> recall = 2^(-5 / 4) = 2^(-1.25) = ~0.4204482
    # next review = last_practice + (-4 * log2(0.70)) = last_practice + 2.05837 days
    assert state.half_life_days == 4.0
    expected_recall = 2.0 ** (-5.0 / 4.0)
    assert abs(state.recall_now - expected_recall) < 1e-9
    expected_due = last_practice + timedelta(days=-4.0 * -0.5145731728297582)
    assert abs((state.next_review_at - expected_due).total_seconds()) < 1.0
