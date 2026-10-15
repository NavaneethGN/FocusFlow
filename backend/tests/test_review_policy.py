"""
tests/test_review_policy.py
Verification tests for Module 3: Review policy and next_review_at.
"""
from datetime import datetime, timezone, timedelta
import pytest

from hlr.predictor import HLRValidationError
from hlr.review_policy import next_review_at

def test_next_review_time():
    last_t = datetime(2026, 10, 15, 12, 0, 0, tzinfo=timezone.utc)
    h = 4.0
    threshold = 0.70
    due_dt = next_review_at(last_t, h, threshold)
    # interval is -4 * log2(0.7) = ~2.05837 days
    expected_dt = last_t + timedelta(days=-4.0 * -0.5145731728297582)
    assert abs((due_dt - expected_dt).total_seconds()) < 1.0
    assert due_dt.tzinfo == timezone.utc

def test_naive_datetime_rejected():
    naive_dt = datetime(2026, 10, 15, 12, 0, 0)  # No tzinfo
    with pytest.raises(HLRValidationError):
        next_review_at(naive_dt, 4.0, 0.70)
