"""
backend/hlr/predictor.py
Pure Python HLR prediction engine.
Settles & Meeder (2016): "A Trainable Spaced Repetition Model for Language Learning".

Equations:
  h = 2 ** (theta . x)
  p_hat = 2 ** (-delta / h)
  review interval = -h * log2(threshold)
"""
import math
from typing import Sequence, Optional
from .config import HLRConfig

class HLRValidationError(ValueError):
    """Raised when input validation for HLR math functions fails."""
    pass

_DEFAULT_CONFIG = HLRConfig()

def _check_finite(val: float, name: str) -> None:
    if not isinstance(val, (int, float)) or isinstance(val, bool) or math.isnan(val) or math.isinf(val):
        raise HLRValidationError(f"Invalid non-finite or non-numeric value for {name}: {val!r}")

def raw_log2_half_life(theta: Sequence[float], x: Sequence[float]) -> float:
    """Computes unclipped raw log2 half-life = theta . x for monitoring and debugging."""
    if len(theta) != len(x):
        raise HLRValidationError(f"Length mismatch: len(theta)={len(theta)} != len(x)={len(x)}")
    
    for idx, (t, v) in enumerate(zip(theta, x)):
        _check_finite(t, f"theta[{idx}]")
        _check_finite(v, f"x[{idx}]")
    
    total = sum(t * v for t, v in zip(theta, x))
    _check_finite(total, "dot_product(theta, x)")
    return total

def predict_half_life(
    theta: Sequence[float],
    x: Sequence[float],
    config: Optional[HLRConfig] = None
) -> float:
    """Computes half-life h = 2^(theta . x) clamped to [h_min_days, h_max_days].
    
    ASSUMPTION: Clamping bounds prevent numerical overflow and underflow, adhering to
    Settles & Meeder (2016) bounded half-life intervals.
    """
    cfg = config or _DEFAULT_CONFIG
    z = raw_log2_half_life(theta, x)
    try:
        h = 2.0 ** z
    except OverflowError:
        h = cfg.h_max_days
    return min(max(h, cfg.h_min_days), cfg.h_max_days)

def predict_recall(
    half_life_days: float,
    delta_days: float,
    config: Optional[HLRConfig] = None
) -> float:
    """Computes recall probability p_hat = 2^(-delta / h) clamped to [p_min, p_max].
    
    Rejects negative delta_days and non-positive half_life_days with HLRValidationError.
    """
    cfg = config or _DEFAULT_CONFIG
    _check_finite(half_life_days, "half_life_days")
    _check_finite(delta_days, "delta_days")
    
    if half_life_days <= 0:
        raise HLRValidationError(f"half_life_days must be positive, got {half_life_days}")
    if delta_days < 0:
        raise HLRValidationError(f"delta_days cannot be negative in core predictor, got {delta_days}")

    p = 2.0 ** (-float(delta_days) / float(half_life_days))
    return min(max(p, cfg.p_min), cfg.p_max)

def predict_next_review_days(
    half_life_days: float,
    threshold: Optional[float] = None,
    config: Optional[HLRConfig] = None
) -> float:
    """Computes days until recall reaches the threshold: Delta = -h * log2(threshold).
    
    Threshold must be strictly within the open interval (0, 1).
    """
    cfg = config or _DEFAULT_CONFIG
    th = cfg.review_threshold if threshold is None else threshold
    _check_finite(half_life_days, "half_life_days")
    _check_finite(th, "threshold")

    if half_life_days <= 0:
        raise HLRValidationError(f"half_life_days must be positive, got {half_life_days}")
    if th <= 0.0 or th >= 1.0:
        raise HLRValidationError(f"threshold must be in (0, 1), got {th}")

    return -float(half_life_days) * math.log2(th)
