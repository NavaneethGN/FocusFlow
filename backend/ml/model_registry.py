"""
backend/ml/model_registry.py
Model registry managing model versions, cryptographic checksums, active model caching,
and non-interfering shadow mode evaluation.
"""
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
import math
import time
from typing import Sequence, List, Dict, Any, Optional, Tuple

from repositories.base import UnitOfWork, ModelVersionRecord
from hlr.config import HLRConfig
from hlr.features import FeatureSpec, RAW_SPEC, SQRT_SPEC, get_spec
from hlr.predictor import HLRValidationError, predict_half_life, predict_recall
from hlr.updater import ModelArtifact, HLR_V0_FIXED

def compute_model_checksum(
    theta: Sequence[float],
    feature_spec: Dict[str, Any],
    training_config: Dict[str, Any]
) -> str:
    """Computes a cryptographically stable SHA256 checksum for model artifacts."""
    canonical_dict = {
        "theta": [round(float(t), 8) for t in theta],
        "feature_spec": {
            "name": feature_spec.get("name"),
            "feature_names": feature_spec.get("feature_names")
        },
        "training_config": {
            k: v for k, v in sorted(training_config.items())
            if isinstance(v, (int, float, str, bool))
        }
    }
    dumped = json.dumps(canonical_dict, sort_keys=True)
    return hashlib.sha256(dumped.encode("utf-8")).hexdigest()

class ModelRegistry:
    """Registry coordinating persisted models, checksum validation, and active model cache."""

    def __init__(self, ttl_seconds: float = 30.0):
        self._ttl_seconds = ttl_seconds
        self._cached_active_record: Optional[ModelVersionRecord] = None
        self._cached_active_artifact: Optional[ModelArtifact] = None
        self._cache_expires_at: float = 0.0
        self._shadow_store: List[Dict[str, Any]] = []

    def invalidate_cache(self) -> None:
        """Invalidates the in-memory active model cache."""
        self._cached_active_record = None
        self._cached_active_artifact = None
        self._cache_expires_at = 0.0

    def seed_default_model(self, uow: UnitOfWork) -> ModelVersionRecord:
        """Seeds hlr_v0_fixed on first startup if no models exist in repository."""
        active = uow.models.get_active()
        if active is not None:
            return active

        all_models = uow.models.list_all()
        if len(all_models) > 0:
            # Active flag missing, pick first or set active
            return uow.models.set_active(all_models[0].id)

        # Register hlr_v0_fixed as the initial provisional launch model
        spec_dict = {
            "name": RAW_SPEC.name,
            "feature_names": list(RAW_SPEC.feature_names)
        }
        cfg_dict = {"status": "provisional_fixed_weights", "note": "Leitner-equivalent baseline"}
        chk = compute_model_checksum(HLR_V0_FIXED.theta, spec_dict, cfg_dict)

        rec = ModelVersionRecord(
            id="hlr-launch-v1",
            name="Launch Model (Raw Counts)",
            version="0.1.0",
            theta=list(HLR_V0_FIXED.theta),
            feature_spec=spec_dict,
            training_config=cfg_dict,
            checksum=chk,
            dataset_snapshot_id=None,
            evaluation_metrics=None,
            validation_status="provisional_fixed_weights",
            active=True,
            created_at=datetime.now(timezone.utc)
        )
        return uow.models.register(rec)

    def register_candidate(
        self,
        artifact: ModelArtifact,
        training_report: Optional[Any] = None,
        dataset_snapshot_id: Optional[str] = None,
        evaluation_metrics: Optional[Dict[str, Any]] = None,
        uow: Optional[UnitOfWork] = None
    ) -> ModelVersionRecord:
        """Registers a candidate model. NEVER activates it upon registration."""
        # 1. Spec and length validation
        expected_len = len(artifact.feature_spec.feature_names)
        if len(artifact.theta) != expected_len:
            raise HLRValidationError(
                f"Theta length {len(artifact.theta)} does not match feature spec '{artifact.feature_spec.name}' count {expected_len}"
            )
        for t in artifact.theta:
            if not isinstance(t, (int, float)) or not math.isfinite(t):
                raise HLRValidationError(f"Non-finite weight encountered in candidate theta: {t!r}")

        spec_dict = {
            "name": artifact.feature_spec.name,
            "feature_names": list(artifact.feature_spec.feature_names)
        }
        cfg_dict = {
            "h_min_days": artifact.config.h_min_days,
            "h_max_days": artifact.config.h_max_days,
            "p_min": artifact.config.p_min,
            "p_max": artifact.config.p_max,
            "review_threshold": artifact.config.review_threshold
        }
        if training_report and hasattr(training_report, "config"):
            cfg_dict.update(training_report.config)

        chk = compute_model_checksum(artifact.theta, spec_dict, cfg_dict)
        model_id = f"hlr-{artifact.feature_spec.name}-{chk[:8]}"

        rec = ModelVersionRecord(
            id=model_id,
            name=artifact.name,
            version="1.0.0",
            theta=list(artifact.theta),
            feature_spec=spec_dict,
            training_config=cfg_dict,
            checksum=chk,
            dataset_snapshot_id=dataset_snapshot_id,
            evaluation_metrics=evaluation_metrics,
            validation_status="candidate",
            active=False,
            created_at=datetime.now(timezone.utc)
        )

        if uow is not None:
            return uow.models.register(rec)
        return rec

    def load_active_model(
        self,
        uow: UnitOfWork,
        bypass_cache: bool = False
    ) -> Tuple[ModelVersionRecord, ModelArtifact]:
        """Loads and validates the current active model, using a TTL cache."""
        now = time.time()
        if not bypass_cache and self._cached_active_record and self._cached_active_artifact:
            if now < self._cache_expires_at:
                return self._cached_active_record, self._cached_active_artifact

        active_rec = uow.models.get_active()
        if active_rec is None:
            active_rec = self.seed_default_model(uow)

        # Verify Checksum Integrity
        computed_chk = compute_model_checksum(
            active_rec.theta,
            active_rec.feature_spec,
            active_rec.training_config
        )
        if computed_chk != active_rec.checksum:
            raise HLRValidationError(
                f"Tampered model detected! Checksum mismatch for active model '{active_rec.id}'"
            )

        spec = get_spec(active_rec.feature_spec["name"])
        if len(active_rec.theta) != len(spec.feature_names):
            raise HLRValidationError(
                f"Active model theta length mismatch: {len(active_rec.theta)} vs spec {len(spec.feature_names)}"
            )

        cfg_dict = active_rec.training_config
        hlr_cfg = HLRConfig(
            h_min_days=cfg_dict.get("h_min_days", 15.0 / 1440.0),
            h_max_days=cfg_dict.get("h_max_days", 270.0),
            p_min=cfg_dict.get("p_min", 0.0001),
            p_max=cfg_dict.get("p_max", 0.9999),
            review_threshold=cfg_dict.get("review_threshold", 0.70)
        )

        artifact = ModelArtifact(
            name=active_rec.name,
            theta=list(active_rec.theta),
            feature_spec=spec,
            config=hlr_cfg
        )

        self._cached_active_record = active_rec
        self._cached_active_artifact = artifact
        self._cache_expires_at = now + self._ttl_seconds

        return active_rec, artifact

    def list_models(self, uow: UnitOfWork) -> List[ModelVersionRecord]:
        """Lists all registered models."""
        models = uow.models.list_all()
        if len(models) == 0:
            self.seed_default_model(uow)
            models = uow.models.list_all()
        return models

    def record_shadow_prediction(
        self,
        session_id: str,
        student_id: str,
        concept_id: str,
        active_prediction: float,
        candidate_model_id: str,
        candidate_prediction: float
    ) -> None:
        """Stores a shadow prediction without affecting active plan scheduling."""
        self._shadow_store.append({
            "session_id": session_id,
            "student_id": student_id,
            "concept_id": concept_id,
            "active_p": active_prediction,
            "candidate_model_id": candidate_model_id,
            "candidate_p": candidate_prediction,
            "recorded_at": datetime.now(timezone.utc).isoformat()
        })

    def get_shadow_predictions(self, session_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Retrieves stored shadow mode predictions for offline comparison."""
        if session_id:
            return [p for p in self._shadow_store if p["session_id"] == session_id]
        return list(self._shadow_store)

GLOBAL_REGISTRY = ModelRegistry()
