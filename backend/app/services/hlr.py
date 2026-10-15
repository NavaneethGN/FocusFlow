import math
from datetime import datetime, timezone, timedelta
from typing import Literal, Tuple

# Paper bounds (Duolingo Half-Life Regression)
# Half-life between 15 minutes and 270 days (~9 months)
H_MIN: float = 15.0 / 1440.0
H_MAX: float = 270.0

# Probability bounds to avoid log(0) and extreme edge saturation
P_MIN: float = 0.0001
P_MAX: float = 0.9999

FeatureSpecType = Literal["raw_counts", "sqrt_counts"]

# Default launch weights:
# theta = [bias, weight_correct, weight_incorrect]
# Bias = 1.0 gives baseline h = 2^1 = 2 days for a fresh concept
# Weight_correct = 1.0 doubles half life (2^(x+1) = 2*2^x)
# Weight_incorrect = -1.0 halves half life (2^(x-1) = 0.5*2^x)
DEFAULT_LAUNCH_THETA = [1.0, 1.0, -1.0]
DEFAULT_FEATURE_SPEC: FeatureSpecType = "raw_counts"


def extract_features(correct_count: int, incorrect_count: int, feature_spec: FeatureSpecType = "raw_counts") -> list[float]:
    """Transforms raw user counts into feature vector x with intercept."""
    c = max(0, correct_count)
    i = max(0, incorrect_count)
    if feature_spec == "sqrt_counts":
        return [1.0, math.sqrt(c), math.sqrt(i)]
    # Default: raw_counts
    return [1.0, float(c), float(i)]


def half_life(theta: list[float], x: list[float]) -> float:
    """Computes estimated half-life h (in days) given weights theta and feature vector x:
    h = 2 ** sum(theta_i * x_i), bounded by [H_MIN, H_MAX].
    """
    if len(theta) != len(x):
        raise ValueError(f"theta length ({len(theta)}) must match x length ({len(x)})")
    
    linear_comb = sum(t * v for t, v in zip(theta, x))
    
    # Protect against float overflow in 2 ** linear_comb
    if linear_comb > 12.0:
        h = H_MAX
    elif linear_comb < -10.0:
        h = H_MIN
    else:
        h = 2.0 ** linear_comb

    return float(min(max(h, H_MIN), H_MAX))


def recall_prob(h: float, delta_days: float) -> float:
    """Computes predicted recall probability p̂ at delta_days since last practice:
    p = 2 ** (-delta_days / h), bounded by [P_MIN, P_MAX].
    """
    h_safe = max(h, H_MIN)
    d_safe = max(0.0, float(delta_days))
    
    power = -d_safe / h_safe
    # Underflow protection
    if power < -20.0:
        return P_MIN
    if power >= 0.0:
        return P_MAX
        
    p = 2.0 ** power
    return float(min(max(p, P_MIN), P_MAX))


def next_review_days(h: float, threshold: float = 0.7) -> float:
    """Computes time interval (in days) until recall probability decays to threshold:
    p = 2 ** (-delta / h) = threshold ==> delta = -h * log2(threshold).
    """
    thresh = min(max(threshold, P_MIN), P_MAX)
    log2_thresh = math.log2(thresh)
    delta = -h * log2_thresh
    return max(H_MIN, float(delta))


def compute_session_concept_update(
    correct_session: int,
    total_session: int,
    last_practiced_at: datetime | None,
    current_correct_total: int,
    current_incorrect_total: int,
    theta: list[float],
    feature_spec: FeatureSpecType = "raw_counts",
    threshold: float = 0.7,
    now: datetime | None = None,
) -> dict:
    """Executes the HLR session close update for a concept:
    1. Computes session observed recall: p = correct / attempts
    2. Computes elapsed delta: delta_days = now - last_practiced_at
    3. Extracts x_before for training records
    4. Updates count totals
    5. Computes updated half_life h_hat and next_review_at
    """
    if now is None:
        now = datetime.now(timezone.utc)
    elif now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    # 1. Session recall
    session_attempts = max(1, total_session)
    p_observed = float(correct_session) / float(session_attempts)

    # 2. Elapsed interval delta_days
    if last_practiced_at is not None:
        if last_practiced_at.tzinfo is None:
            last_practiced = last_practiced_at.replace(tzinfo=timezone.utc)
        else:
            last_practiced = last_practiced_at
        delta_seconds = max(0.0, (now - last_practiced).total_seconds())
        delta_days = delta_seconds / 86400.0
    else:
        # Initial introduction delta (0.0 days)
        delta_days = 0.0

    # 3. x_before feature vector prior to session update
    x_before = extract_features(current_correct_total, current_incorrect_total, feature_spec)

    # 4. Update count totals
    new_correct_total = current_correct_total + correct_session
    new_incorrect_total = current_incorrect_total + (session_attempts - correct_session)

    # 5. Extract x_after and calculate new half-life h_hat
    x_after = extract_features(new_correct_total, new_incorrect_total, feature_spec)
    new_h_hat = half_life(theta, x_after)

    # 6. Next review interval & timestamp
    review_window_days = next_review_days(new_h_hat, threshold=threshold)
    next_review_at = now + timedelta(days=review_window_days)

    # Immediate recall right after practice (delta = 0)
    p_hat_cached = recall_prob(new_h_hat, 0.0)

    return {
        "p_observed": p_observed,
        "delta_days": delta_days,
        "x_before": x_before,
        "new_correct_total": new_correct_total,
        "new_incorrect_total": new_incorrect_total,
        "h_hat": new_h_hat,
        "p_hat_cached": p_hat_cached,
        "next_review_at": next_review_at,
        "now": now,
    }


def generate_forgetting_curve_points(
    h: float,
    threshold: float = 0.7,
    max_days: float | None = None,
    num_points: int = 40,
) -> list[dict[str, float]]:
    """Generates (day, recall_probability) curve points for chart plotting."""
    review_day = next_review_days(h, threshold=threshold)
    if max_days is None:
        max_days = max(review_day * 2.2, 7.0)

    step = max_days / float(num_points - 1)
    points = []
    for i in range(num_points):
        d = round(i * step, 2)
        prob = round(recall_prob(h, d), 4)
        points.append({
            "day": d,
            "probability": prob,
            "threshold": threshold,
        })
    return points
