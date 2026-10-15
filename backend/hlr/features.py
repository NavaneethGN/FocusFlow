"""
backend/hlr/features.py
Feature extraction and specification for Half-Life Regression.
Pure Python, standard library only.

Settles & Meeder (2016):
- Baseline features: [1.0, n_right, n_wrong]
- Square-root transformed features: [1.0, sqrt(n_right), sqrt(n_wrong)]
Note: times_seen is omitted because times_seen = n_right + n_wrong (collinear).
"""
import hashlib
import math
from dataclasses import dataclass
from typing import Callable, List, Optional, Dict, Any
from .predictor import HLRValidationError

@dataclass(frozen=True)
class ConceptCounts:
    """Practice outcome counts for a concept.
    Strictly validates non-negative finite integers. Rejects bool, float, NaN, and negative values.
    """
    n_right: int
    n_wrong: int

    def __post_init__(self):
        for name, val in [("n_right", self.n_right), ("n_wrong", self.n_wrong)]:
            if isinstance(val, bool) or not isinstance(val, int):
                raise HLRValidationError(f"{name} must be a strict integer, got {type(val).__name__}: {val!r}")
            if val < 0:
                raise HLRValidationError(f"{name} must be non-negative, got {val}")

@dataclass(frozen=True)
class FeatureSpec:
    """Specification of feature ordering, naming, version, and transformation."""
    name: str
    feature_names: List[str]
    feature_order_version: str
    transform: Callable[[ConceptCounts, Optional[Dict[str, Any]]], List[float]]

def _raw_transform(counts: ConceptCounts, context: Optional[Dict[str, Any]] = None) -> List[float]:
    return [1.0, float(counts.n_right), float(counts.n_wrong)]

def _sqrt_transform(counts: ConceptCounts, context: Optional[Dict[str, Any]] = None) -> List[float]:
    return [1.0, math.sqrt(float(counts.n_right)), math.sqrt(float(counts.n_wrong))]

DIFFICULTY_MAP: Dict[str, float] = {
    "easy": -1.0,
    "medium": 0.0,
    "hard": 1.0,
}

DATA_QUALITY_METRICS: Dict[str, int] = {
    "missing_difficulty_count": 0,
}

def _sqrt_difficulty_transform(counts: ConceptCounts, context: Optional[Dict[str, Any]] = None) -> List[float]:
    base_vec = [1.0, math.sqrt(float(counts.n_right)), math.sqrt(float(counts.n_wrong))]
    diff_score = 0.0
    if context and "difficulty" in context and context["difficulty"] is not None:
        diff_str = str(context["difficulty"]).strip().lower()
        if diff_str in DIFFICULTY_MAP:
            diff_score = DIFFICULTY_MAP[diff_str]
        else:
            DATA_QUALITY_METRICS["missing_difficulty_count"] += 1
            diff_score = 0.0
    elif context and "difficulty_score" in context and context["difficulty_score"] is not None:
        try:
            diff_score = float(context["difficulty_score"])
        except (ValueError, TypeError):
            DATA_QUALITY_METRICS["missing_difficulty_count"] += 1
            diff_score = 0.0
    else:
        DATA_QUALITY_METRICS["missing_difficulty_count"] += 1
        diff_score = 0.0

    return base_vec + [diff_score]

RAW_SPEC = FeatureSpec(
    name="raw_counts",
    feature_names=["bias", "n_right", "n_wrong"],
    feature_order_version="1.0",
    transform=_raw_transform,
)

SQRT_SPEC = FeatureSpec(
    name="sqrt_counts",
    feature_names=["bias", "sqrt_n_right", "sqrt_n_wrong"],
    feature_order_version="1.0",
    transform=_sqrt_transform,
)

SQRT_DIFFICULTY_SPEC = FeatureSpec(
    name="sqrt_counts_difficulty",
    feature_names=["bias", "sqrt_n_right", "sqrt_n_wrong", "difficulty_score"],
    feature_order_version="1.0",
    transform=_sqrt_difficulty_transform,
)

_SPECS: Dict[str, FeatureSpec] = {
    RAW_SPEC.name: RAW_SPEC,
    SQRT_SPEC.name: SQRT_SPEC,
    SQRT_DIFFICULTY_SPEC.name: SQRT_DIFFICULTY_SPEC,
}

def register_spec(spec: FeatureSpec) -> None:
    """Registers a feature specification."""
    _SPECS[spec.name] = spec

def get_spec(name: str) -> FeatureSpec:
    """Retrieves a feature spec by name. Raises HLRValidationError if unknown."""
    if name not in _SPECS:
        raise HLRValidationError(f"Unknown feature spec '{name}'. Available: {list(_SPECS.keys())}")
    return _SPECS[name]

def extract_features(
    counts: ConceptCounts,
    spec: FeatureSpec,
    context: Optional[Dict[str, Any]] = None
) -> List[float]:
    """Extracts the feature vector according to the given FeatureSpec.
    
    Returns [1.0, f(n_right), f(n_wrong)] (or extended with context if spec supports it).
    """
    if not isinstance(counts, ConceptCounts):
        raise HLRValidationError(f"Expected ConceptCounts instance, got {type(counts).__name__}")
    return spec.transform(counts, context)

def is_new(counts: ConceptCounts) -> bool:
    """Returns True if the concept has never been practiced (0 right, 0 wrong)."""
    return (counts.n_right + counts.n_wrong) == 0

def spec_hash(spec: FeatureSpec) -> str:
    """Generates a stable, reproducible SHA-256 hash for a FeatureSpec based on its
    name, version, and exact feature ordering.
    """
    representation = f"{spec.name}::v{spec.feature_order_version}::{','.join(spec.feature_names)}"
    return hashlib.sha256(representation.encode("utf-8")).hexdigest()
