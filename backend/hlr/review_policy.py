"""
backend/hlr/review_policy.py
Review scheduling policy based on HLR recall degradation.
Pure Python, standard library only.
"""
from datetime import datetime, timezone, timedelta
from typing import Optional

from .config import HLRConfig
from .predictor import HLRValidationError, predict_next_review_days

def next_review_at(
    last_practiced_at: datetime,
    half_life_days: float,
    threshold: Optional[float] = None,
    config: Optional[HLRConfig] = None
) -> datetime:
    """Calculates the timezone-aware UTC datetime at which recall falls to threshold.
    
    Rejects timezone-naive datetimes.
    """
    if last_practiced_at.tzinfo is None or last_practiced_at.tzinfo.utcoffset(last_practiced_at) is None:
        raise HLRValidationError(f"last_practiced_at must be timezone-aware, got naive {last_practiced_at!r}")
    
    interval_days = predict_next_review_days(half_life_days, threshold, config)
    target_dt = last_practiced_at + timedelta(days=interval_days)
    return target_dt.astimezone(timezone.utc)
