"""
legacy_reference.py
FROZEN REFERENCE: Verbatim copies of original HLR functions and constants from main.py.
DO NOT EDIT. This is the ground-truth baseline for characterization and regression tests.
"""
import math
from typing import List

H_MIN: float = 15.0 / 1440.0   # 15 minutes in days
H_MAX: float = 270.0          # ~9 months
P_MIN: float = 0.0001
P_MAX: float = 0.9999
DEFAULT_THRESHOLD: float = 0.70

LAUNCH_THETA = [0.0, 1.0, -1.0]

def half_life(theta: List[float], x: List[float]) -> float:
    """Computes half-life h = 2^(theta . x) clamped to [H_MIN, H_MAX]."""
    exponent = sum(t * v for t, v in zip(theta, x))
    h = 2.0 ** exponent
    return min(max(h, H_MIN), H_MAX)

def recall_prob(h: float, delta_days: float) -> float:
    """Computes recall probability p_hat = 2^(-delta / h) clamped to [P_MIN, P_MAX]."""
    if h <= 0:
        return P_MIN
    p = 2.0 ** (-max(0.0, delta_days) / h)
    return min(max(p, P_MIN), P_MAX)

def next_review_days(h: float, threshold: float = DEFAULT_THRESHOLD) -> float:
    """Returns days until recall falls to the target retention threshold."""
    if threshold <= 0 or threshold >= 1:
        threshold = DEFAULT_THRESHOLD
    return -h * math.log2(threshold)
