import math
import pytest
from app.services.hlr import (
    H_MIN,
    H_MAX,
    P_MIN,
    P_MAX,
    DEFAULT_LAUNCH_THETA,
    extract_features,
    half_life,
    recall_prob,
    next_review_days,
    compute_session_concept_update,
    generate_forgetting_curve_points,
)


def test_hlr_math_invariants():
    """Core paper invariants:
    1. When delta equals h, recall probability must be exactly 0.5.
    2. When delta is 0, recall probability must be at its upper bound (P_MAX / 1.0).
    """
    test_half_lives = [0.5, 1.0, 2.0, 5.0, 14.0, 60.0]
    for h in test_half_lives:
        p_at_h = recall_prob(h=h, delta_days=h)
        assert pytest.approx(p_at_h, rel=1e-4) == 0.5, f"p at delta=h must be 0.5 for h={h}"

        p_at_zero = recall_prob(h=h, delta_days=0.0)
        assert pytest.approx(p_at_zero, rel=1e-4) == P_MAX


def test_hlr_bounds():
    """Half-life and probability must respect the paper's specified bounds."""
    # Extreme high linear combination
    h_huge = half_life([100.0, 100.0], [1.0, 1.0])
    assert h_huge <= H_MAX
    assert pytest.approx(h_huge) == H_MAX

    # Extreme low linear combination
    h_tiny = half_life([-100.0, -100.0], [1.0, 1.0])
    assert h_tiny >= H_MIN
    assert pytest.approx(h_tiny) == H_MIN

    # Long delta decay
    p_far = recall_prob(h=1.0, delta_days=500.0)
    assert p_far >= P_MIN


def test_threshold_review_interval():
    """Review interval at 0.5 must equal h, and at 0.7 must be -h*log2(0.7)."""
    h = 4.0
    # At threshold 0.5: -4 * log2(0.5) = -4 * (-1) = 4.0 days
    delta_50 = next_review_days(h, threshold=0.5)
    assert pytest.approx(delta_50, rel=1e-4) == 4.0

    # At threshold 0.7: -4 * log2(0.7) ≈ 4.0 * 0.514573 ≈ 2.058 days
    delta_70 = next_review_days(h, threshold=0.7)
    expected_delta_70 = -4.0 * math.log2(0.7)
    assert pytest.approx(delta_70, rel=1e-4) == expected_delta_70

    # Verify that evaluating recall_prob at next_review_days produces the threshold
    p_at_review = recall_prob(h, delta_70)
    assert pytest.approx(p_at_review, rel=1e-3) == 0.7


def test_launch_weights_effect():
    """Verify launch weights behaviour:
    With theta = [1.0, 1.0, -1.0]:
    Baseline (0,0): h = 2^1 = 2.0
    1 correct: h = 2^(1+1) = 4.0 (doubles)
    1 wrong: h = 2^(1-1) = 1.0 (halves)
    """
    x_base = extract_features(0, 0, "raw_counts")
    h_base = half_life(DEFAULT_LAUNCH_THETA, x_base)
    assert pytest.approx(h_base, rel=1e-4) == 2.0

    x_correct = extract_features(1, 0, "raw_counts")
    h_correct = half_life(DEFAULT_LAUNCH_THETA, x_correct)
    assert pytest.approx(h_correct, rel=1e-4) == 4.0
    assert h_correct > h_base

    x_wrong = extract_features(0, 1, "raw_counts")
    h_wrong = half_life(DEFAULT_LAUNCH_THETA, x_wrong)
    assert pytest.approx(h_wrong, rel=1e-4) == 1.0
    assert h_wrong < h_base


def test_feature_transform_sqrt():
    """Verify sqrt_counts feature extractor matches paper specification."""
    x = extract_features(4, 9, "sqrt_counts")
    assert x == [1.0, 2.0, 3.0]


def test_session_concept_update():
    """Verify complete session-close calculation."""
    # Concept with initial 1 correct, 0 incorrect
    result = compute_session_concept_update(
        correct_session=2,
        total_session=2,
        last_practiced_at=None,
        current_correct_total=1,
        current_incorrect_total=0,
        theta=DEFAULT_LAUNCH_THETA,
        feature_spec="raw_counts",
        threshold=0.7,
    )

    assert result["p_observed"] == 1.0
    assert result["delta_days"] == 0.0
    assert result["x_before"] == [1.0, 1.0, 0.0]
    assert result["new_correct_total"] == 3
    assert result["new_incorrect_total"] == 0
    # new h = 2^(1 + 3) = 16.0 days
    assert pytest.approx(result["h_hat"], rel=1e-4) == 16.0
    assert result["next_review_at"] > result["now"]


def test_forgetting_curve_points():
    """Verify generation of forgetting curve points."""
    points = generate_forgetting_curve_points(h=2.0, threshold=0.7, num_points=10)
    assert len(points) == 10
    # Day 0 probability should be max
    assert points[0]["day"] == 0.0
    assert points[0]["probability"] == pytest.approx(P_MAX, rel=1e-2)
    # Probability decays monotonically
    for i in range(len(points) - 1):
        assert points[i]["probability"] >= points[i + 1]["probability"]
