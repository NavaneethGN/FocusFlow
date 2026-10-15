"""
tests/test_features.py
Verification tests for Module 2: Versioned feature extraction.
"""
import math
import pytest

from hlr.predictor import HLRValidationError
from hlr.features import (
    ConceptCounts,
    FeatureSpec,
    RAW_SPEC,
    SQRT_SPEC,
    extract_features,
    is_new,
    get_spec,
    spec_hash,
)

def test_raw_example():
    counts = ConceptCounts(n_right=3, n_wrong=1)
    x = extract_features(counts, RAW_SPEC)
    assert x == [1.0, 3.0, 1.0]

def test_sqrt_example():
    counts = ConceptCounts(n_right=3, n_wrong=1)
    x = extract_features(counts, SQRT_SPEC)
    assert x[0] == 1.0
    assert abs(x[1] - math.sqrt(3.0)) < 1e-7
    assert x[2] == 1.0

def test_another_raw_example():
    counts = ConceptCounts(n_right=5, n_wrong=3)
    x = extract_features(counts, RAW_SPEC)
    assert x == [1.0, 5.0, 3.0]

def test_new_concept():
    counts = ConceptCounts(n_right=0, n_wrong=0)
    x = extract_features(counts, RAW_SPEC)
    assert x == [1.0, 0.0, 0.0]
    assert is_new(counts) is True

    not_new = ConceptCounts(n_right=1, n_wrong=0)
    assert is_new(not_new) is False

def test_determinism():
    counts = ConceptCounts(n_right=7, n_wrong=2)
    first = extract_features(counts, RAW_SPEC)
    for _ in range(1000):
        assert extract_features(counts, RAW_SPEC) == first

def test_negative_count_rejected():
    with pytest.raises(HLRValidationError):
        ConceptCounts(n_right=-1, n_wrong=0)

    with pytest.raises(HLRValidationError):
        ConceptCounts(n_right=0, n_wrong=-2)

def test_non_integer_count_rejected():
    with pytest.raises(HLRValidationError):
        ConceptCounts(n_right=2.5, n_wrong=1)  # float

    with pytest.raises(HLRValidationError):
        ConceptCounts(n_right=float("nan"), n_wrong=1)

    with pytest.raises(HLRValidationError):
        ConceptCounts(n_right=True, n_wrong=1)  # bool rejected

    with pytest.raises(HLRValidationError):
        ConceptCounts(n_right=1, n_wrong=False)

def test_spec_hash_stability_and_order_sensitivity():
    # Same spec produces identical hash
    hash1 = spec_hash(RAW_SPEC)
    hash2 = spec_hash(RAW_SPEC)
    assert hash1 == hash2

    # Changing feature ordering must produce a different hash
    reordered_spec = FeatureSpec(
        name="raw_counts",
        feature_names=["bias", "n_wrong", "n_right"],
        feature_order_version="1.0",
        transform=RAW_SPEC.transform
    )
    assert spec_hash(reordered_spec) != hash1

def test_get_spec_lookup():
    assert get_spec("raw_counts") == RAW_SPEC
    assert get_spec("sqrt_counts") == SQRT_SPEC
    with pytest.raises(HLRValidationError):
        get_spec("unknown_spec_xyz")
