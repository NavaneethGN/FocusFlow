# backend/hlr
"""FocusFlow Half-Life Regression (HLR) Pure Python Package.
Standard library only: no DB, HTTP, FastAPI or Gemini imports.
"""
from .config import HLRConfig
from .predictor import (
    HLRValidationError,
    predict_half_life,
    predict_recall,
    predict_next_review_days,
    raw_log2_half_life,
)
from .features import (
    ConceptCounts,
    FeatureSpec,
    RAW_SPEC,
    SQRT_SPEC,
    extract_features,
    is_new,
    get_spec,
    spec_hash,
)
from .review_policy import next_review_at
from .updater import (
    ModelArtifact,
    HLR_V0_FIXED,
    LAUNCH_THETA,
    ConceptStateResult,
    apply_outcome,
    compute_state,
)
from .trainer import (
    TrainerConfig,
    TrainingReport,
    compute_loss_and_gradient,
    gradient_check,
    train_hlr,
)

__all__ = [
    "HLRConfig",
    "HLRValidationError",
    "predict_half_life",
    "predict_recall",
    "predict_next_review_days",
    "raw_log2_half_life",
    "ConceptCounts",
    "FeatureSpec",
    "RAW_SPEC",
    "SQRT_SPEC",
    "extract_features",
    "is_new",
    "get_spec",
    "spec_hash",
    "next_review_at",
    "ModelArtifact",
    "HLR_V0_FIXED",
    "LAUNCH_THETA",
    "ConceptStateResult",
    "apply_outcome",
    "compute_state",
    "TrainerConfig",
    "TrainingReport",
    "compute_loss_and_gradient",
    "gradient_check",
    "train_hlr",
]
