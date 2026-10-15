"""
tests/test_predictor.py
Verification tests for Module 1: pure math predictor and config.
"""
import math
import os
import random
import sys
import pytest
from hypothesis import given, strategies as st

from hlr.config import HLRConfig
from hlr.predictor import (
    HLRValidationError,
    predict_half_life,
    predict_recall,
    predict_next_review_days,
    raw_log2_half_life,
)
import main
from tests import legacy_reference

def test_delta_equals_half_life():
    h = 4.0
    p = predict_recall(h, 4.0)
    assert abs(p - 0.5) < 1e-9

def test_double_half_life():
    h = 4.0
    p = predict_recall(h, 8.0)
    assert abs(p - 0.25) < 1e-9

def test_zero_elapsed_capped():
    h = 4.0
    p = predict_recall(h, 0.0)
    assert p == 0.9999

def test_monotonic_in_delta():
    h = 5.0
    prev_p = 1.0
    for d in [0.0, 0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 20.0, 50.0, 100.0]:
        p = predict_recall(h, d)
        assert p <= prev_p
        prev_p = p

def test_monotonic_in_half_life():
    delta = 3.0
    prev_p = 0.0
    for h in [0.1, 0.5, 1.0, 2.0, 4.0, 10.0, 50.0, 100.0, 200.0]:
        p = predict_recall(h, delta)
        assert p >= prev_p
        prev_p = p

def test_review_at_point_seven():
    h = 4.0
    interval = predict_next_review_days(h, 0.70)
    expected = -4.0 * math.log2(0.70)  # ~2.05837
    assert abs(interval - expected) < 1e-9
    assert abs(interval - 2.05837) < 1e-3

def test_review_at_half():
    for h in [0.5, 1.0, 4.0, 15.0, 200.0]:
        interval = predict_next_review_days(h, 0.5)
        assert abs(interval - h) < 1e-9

def test_upper_bound():
    theta = [0.0, 1.0, 0.0]
    x = [1.0, 30.0, 0.0]
    h = predict_half_life(theta, x)
    assert h == 270.0

def test_lower_bound():
    theta = [0.0, 0.0, -1.0]
    x = [1.0, 0.0, 30.0]
    h = predict_half_life(theta, x)
    assert abs(h - (15.0 / 1440.0)) < 1e-12

def test_raw_vs_bounded():
    theta = [0.0, 1.0, 0.0]
    x = [1.0, 30.0, 0.0]
    raw = raw_log2_half_life(theta, x)
    h = predict_half_life(theta, x)
    assert raw == 30.0
    assert h == 270.0

def test_bad_inputs_raise_validation_error():
    theta = [0.0, 1.0, -1.0]
    x_short = [1.0, 2.0]
    with pytest.raises(HLRValidationError):
        predict_half_life(theta, x_short)

    with pytest.raises(HLRValidationError):
        predict_half_life([float("nan"), 1.0, 0.0], [1.0, 1.0, 1.0])

    with pytest.raises(HLRValidationError):
        predict_half_life([float("inf"), 1.0, 0.0], [1.0, 1.0, 1.0])

    with pytest.raises(HLRValidationError):
        predict_recall(4.0, -1.0)  # Core predictor rejects negative delta

    with pytest.raises(HLRValidationError):
        predict_recall(0.0, 2.0)   # Non-positive half life

    with pytest.raises(HLRValidationError):
        predict_recall(-2.0, 2.0)

    with pytest.raises(HLRValidationError):
        predict_next_review_days(4.0, 0.0)  # threshold <= 0

    with pytest.raises(HLRValidationError):
        predict_next_review_days(4.0, 1.0)  # threshold >= 1

    with pytest.raises(HLRValidationError):
        predict_next_review_days(4.0, -0.5)

def test_legacy_wrapper_negative_delta_behavior():
    """main.recall_prob clamps negative delta to 0, while core predict_recall raises."""
    legacy_res = main.recall_prob(4.0, -1.0)
    assert legacy_res == 0.9999
    with pytest.raises(HLRValidationError):
        predict_recall(4.0, -1.0)

def test_legacy_parity_random_grid():
    """10,000 random finite inputs match legacy_reference within 1e-12."""
    rng = random.Random(42)
    cfg = HLRConfig()

    for _ in range(10000):
        theta = [rng.uniform(-3.0, 3.0) for _ in range(3)]
        x = [1.0, float(rng.randint(0, 30)), float(rng.randint(0, 30))]
        delta = rng.uniform(0.0, 100.0)
        th = rng.uniform(0.01, 0.99)

        # Legacy
        h_leg = legacy_reference.half_life(theta, x)
        p_leg = legacy_reference.recall_prob(h_leg, delta)
        rev_leg = legacy_reference.next_review_days(h_leg, th)

        # New pure math
        h_new = predict_half_life(theta, x, cfg)
        p_new = predict_recall(h_new, delta, cfg)
        rev_new = predict_next_review_days(h_new, th, cfg)

        assert abs(h_new - h_leg) <= 1e-12
        assert abs(p_new - p_leg) <= 1e-12
        assert abs(rev_new - rev_leg) <= 1e-12

def test_hlr_package_pure_python_isolation():
    """Ensure backend/hlr imports no DB, HTTP, FastAPI or framework code."""
    hlr_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "hlr"))
    forbidden_terms = ["fastapi", "sqlalchemy", "requests", "httpx", "uvicorn", "pydantic", "sqlite"]
    for root, _, files in os.walk(hlr_dir):
        for f in files:
            if f.endswith(".py"):
                path = os.path.join(root, f)
                with open(path, "r", encoding="utf-8") as fh:
                    content = fh.read().lower()
                    for term in forbidden_terms:
                        assert f"import {term}" not in content, f"HLR module {f} imports {term}"
                        assert f"from {term}" not in content, f"HLR module {f} imports from {term}"

@given(
    theta=st.lists(st.floats(min_value=-10.0, max_value=10.0, allow_nan=False, allow_infinity=False), min_size=3, max_size=3),
    x=st.lists(st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False), min_size=3, max_size=3),
    delta=st.floats(min_value=0.0, max_value=1000.0, allow_nan=False, allow_infinity=False),
)
def test_hypothesis_hlr_properties(theta, x, delta):
    """Property test using Hypothesis: bounds and ranges are strictly respected."""
    cfg = HLRConfig()
    h = predict_half_life(theta, x, cfg)
    assert cfg.h_min_days <= h <= cfg.h_max_days

    p = predict_recall(h, delta, cfg)
    assert cfg.p_min <= p <= cfg.p_max
