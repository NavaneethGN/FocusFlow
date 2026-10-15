"""
backend/hlr/updater.py
HLR model artifact, state transition updater, and Leitner-equivalent launch model.
Pure Python, standard library only.
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone
import math
from typing import List, Optional, Dict, Any

from .config import HLRConfig
from .features import ConceptCounts, FeatureSpec, RAW_SPEC, extract_features, is_new
from .predictor import HLRValidationError, predict_half_life, predict_recall
from .review_policy import next_review_at

@dataclass(frozen=True)
class ModelArtifact:
    """Indivisible artifact bundling model weights, feature specification, and bounds config."""
    name: str
    theta: List[float]
    feature_spec: FeatureSpec
    config: HLRConfig = field(default_factory=HLRConfig)

    def __post_init__(self):
        if len(self.theta) != len(self.feature_spec.feature_names):
            raise HLRValidationError(
                f"Model '{self.name}' dimension mismatch: len(theta)={len(self.theta)} "
                f"!= len({self.feature_spec.name})={len(self.feature_spec.feature_names)}"
            )
        for idx, t in enumerate(self.theta):
            if not isinstance(t, (int, float)) or isinstance(t, bool) or math.isnan(t) or math.isinf(t):
                raise HLRValidationError(f"Invalid non-finite theta[{idx}]: {t!r}")

# ---------------------------------------------------------------------------
# Launch Model: hlr_v0_fixed
# PROVISIONAL and Leitner-equivalent:
# theta = [0.0, 1.0, -1.0] with raw_counts [1, n_right, n_wrong].
# Every correct answer doubles half-life (2^1 = 2); every incorrect answer halves it (2^-1 = 0.5).
# This is NOT the Settles & Meeder (2016) trained model; it is the baseline every
# trained model must beat.
# ---------------------------------------------------------------------------
HLR_V0_FIXED = ModelArtifact(
    name="hlr_v0_fixed",
    theta=[0.0, 1.0, -1.0],
    feature_spec=RAW_SPEC,
    config=HLRConfig()
)

LAUNCH_THETA = HLR_V0_FIXED.theta

@dataclass(frozen=True)
class ConceptStateResult:
    """Computed state for a concept under an HLR model."""
    half_life_days: float
    recall_now: Optional[float]
    next_review_at: datetime
    is_new: bool

def apply_outcome(counts: ConceptCounts, n_right_new: int, n_wrong_new: int) -> ConceptCounts:
    """Pure function returning a new ConceptCounts object with updated tally."""
    if isinstance(n_right_new, bool) or not isinstance(n_right_new, int) or n_right_new < 0:
        raise HLRValidationError(f"n_right_new must be a non-negative int, got {n_right_new!r}")
    if isinstance(n_wrong_new, bool) or not isinstance(n_wrong_new, int) or n_wrong_new < 0:
        raise HLRValidationError(f"n_wrong_new must be a non-negative int, got {n_wrong_new!r}")
    return ConceptCounts(
        n_right=counts.n_right + n_right_new,
        n_wrong=counts.n_wrong + n_wrong_new
    )

def compute_state(
    counts: ConceptCounts,
    model: ModelArtifact,
    last_practiced_at: Optional[datetime],
    now: datetime,
    threshold: Optional[float] = None,
    context: Optional[Dict[str, Any]] = None
) -> ConceptStateResult:
    """Computes the full HLR state: half-life, recall probability at `now`, and next review datetime.
    
    For a never-practiced concept: returns recall_now=None and next_review_at=now.
    """
    if now.tzinfo is None or now.tzinfo.utcoffset(now) is None:
        raise HLRValidationError(f"now must be timezone-aware, got naive {now!r}")
    
    x = extract_features(counts, model.feature_spec, context)
    h = predict_half_life(model.theta, x, model.config)

    if is_new(counts) or last_practiced_at is None:
        return ConceptStateResult(
            half_life_days=h,
            recall_now=None,
            next_review_at=now.astimezone(timezone.utc),
            is_new=True
        )

    if last_practiced_at.tzinfo is None or last_practiced_at.tzinfo.utcoffset(last_practiced_at) is None:
        raise HLRValidationError(f"last_practiced_at must be timezone-aware, got naive {last_practiced_at!r}")

    delta_days = max(0.0, (now - last_practiced_at).total_seconds() / 86400.0)
    recall = predict_recall(h, delta_days, model.config)
    th = threshold if threshold is not None else model.config.review_threshold
    rev_dt = next_review_at(last_practiced_at, h, th, model.config)

    return ConceptStateResult(
        half_life_days=h,
        recall_now=recall,
        next_review_at=rev_dt,
        is_new=False
    )
