"""
backend/ml/promotion.py
Gated promotion and rollback engine for HLR models.
Enforces multi-stage validation gates, atomic activation transactions, and comprehensive audit logs.
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone
import math
from typing import Sequence, List, Dict, Any, Optional

from repositories.base import UnitOfWork, ModelVersionRecord
from hlr.predictor import HLRValidationError
from .model_registry import GLOBAL_REGISTRY, compute_model_checksum

@dataclass
class PromotionGateReport:
    candidate_id: str
    passed: bool
    reasons: List[str]
    evaluated_at: str
    metrics: Dict[str, Any]

@dataclass
class AuditLogEntry:
    action: str  # 'promote' | 'rollback'
    model_id: str
    approver: str
    timestamp_utc: str
    reasons: List[str]

AUDIT_LOGS: List[AuditLogEntry] = []

def run_promotion_gates(
    candidate: ModelVersionRecord,
    active_model: Optional[ModelVersionRecord],
    temporal_eval: Optional[Dict[str, Any]] = None,
    holdout_eval: Optional[Dict[str, Any]] = None,
    training_report: Optional[Any] = None
) -> PromotionGateReport:
    """Evaluates candidate against strict production safety gates."""
    reasons: List[str] = []
    now_str = datetime.now(timezone.utc).isoformat()

    # Gate 1: Finite theta weights
    if not all(isinstance(t, (int, float)) and math.isfinite(t) for t in candidate.theta):
        reasons.append("Candidate theta contains non-finite values (NaN or Inf)")

    # Gate 2: Feature spec match
    spec_names = candidate.feature_spec.get("feature_names", [])
    if len(candidate.theta) != len(spec_names):
        reasons.append(
            f"Candidate theta length {len(candidate.theta)} does not match spec feature count {len(spec_names)}"
        )

    # Gate 3: Bounds fraction check
    if training_report and hasattr(training_report, "bounds_fraction"):
        if training_report.bounds_fraction > 0.35:
            reasons.append(
                f"Candidate share of predictions at bounds {training_report.bounds_fraction:.2%} exceeds 35% limit"
            )

    # Gate 4: Evaluation results check (Temporal & Holdout)
    metrics_summary = dict(candidate.evaluation_metrics or {})
    if temporal_eval:
        metrics_summary["temporal"] = temporal_eval
        for k in ("beats_leitner", "mae", "leitner_mae", "max_calibration_error"):
            if k in temporal_eval and k not in metrics_summary:
                metrics_summary[k] = temporal_eval[k]
    if holdout_eval:
        metrics_summary["holdout"] = holdout_eval
        for k in ("beats_leitner", "mae", "leitner_mae", "max_calibration_error"):
            if k in holdout_eval and k not in metrics_summary:
                metrics_summary[k] = holdout_eval[k]

    # Check that candidate beats Leitner baseline (hlr_v0_fixed)
    leitner_beat = metrics_summary.get("beats_leitner", False)
    cand_mae = metrics_summary.get("mae")
    leitner_mae = metrics_summary.get("leitner_mae")
    if not leitner_beat:
        if cand_mae is not None and leitner_mae is not None and cand_mae < leitner_mae:
            pass  # beats leitner
        else:
            reasons.append("Candidate does not beat Leitner baseline (hlr_v0_fixed)")

    # Check candidate does not degrade active model beyond tolerance
    if active_model and active_model.evaluation_metrics:
        act_mae = active_model.evaluation_metrics.get("mae")
        cand_mae = metrics_summary.get("mae")
        if act_mae is not None and cand_mae is not None:
            if cand_mae > act_mae + 0.05:
                reasons.append(f"Candidate MAE ({cand_mae:.4f}) degrades active model MAE ({act_mae:.4f}) beyond 0.05 tolerance")

    # Calibration error gate
    max_cal_err = metrics_summary.get("max_calibration_error")
    if max_cal_err is not None and max_cal_err > 0.20:
        reasons.append(f"Maximum bin calibration error {max_cal_err:.3f} exceeds 0.20 limit")

    passed = len(reasons) == 0
    return PromotionGateReport(
        candidate_id=candidate.id or "unknown",
        passed=passed,
        reasons=reasons,
        evaluated_at=now_str,
        metrics=metrics_summary
    )

def promote_model(
    model_id: str,
    approver: str,
    role: str,
    uow: UnitOfWork,
    gate_override_reasons: Optional[List[str]] = None,
    evaluation_evidence: Optional[Dict[str, Any]] = None
) -> ModelVersionRecord:
    """Promotes a candidate model to active status inside a single transaction."""
    # Authorization Guard
    if role.lower() != "admin":
        raise HLRValidationError("Unauthorized: Only users with 'admin' role can promote models")

    candidate = uow.models.get(model_id)
    if candidate is None:
        raise HLRValidationError(f"Model with id '{model_id}' not found in registry")

    active_rec = uow.models.get_active()

    # Run Promotion Gates
    gate_report = run_promotion_gates(
        candidate=candidate,
        active_model=active_rec,
        temporal_eval=evaluation_evidence.get("temporal") if evaluation_evidence else None,
        holdout_eval=evaluation_evidence.get("holdout") if evaluation_evidence else None
    )

    if not gate_report.passed and not gate_override_reasons:
        # Save failure report on candidate record
        reasons_msg = "; ".join(gate_report.reasons)
        raise HLRValidationError(f"Promotion gate failure: {reasons_msg}")

    # Atomic Activation in UnitOfWork
    activated_record = uow.models.set_active(model_id)

    # Invalidate cached concept state versions so states from different weights never mix
    all_states = uow.concept_states.list_by_student(None)
    for cs in all_states:
        # Stale state marker or recompute flag
        cs.model_version = f"{activated_record.id}:stale"
        uow.concept_states.upsert(cs)

    # Invalidate registry cache
    GLOBAL_REGISTRY.invalidate_cache()

    # Record Audit Log
    AUDIT_LOGS.append(AuditLogEntry(
        action="promote",
        model_id=model_id,
        approver=approver,
        timestamp_utc=datetime.now(timezone.utc).isoformat(),
        reasons=gate_report.reasons or ["Passed all safety gates"]
    ))

    return activated_record

def rollback_model(
    to_model_id: str,
    approver: str,
    role: str,
    uow: UnitOfWork
) -> ModelVersionRecord:
    """Rolls back the active model to an earlier registered version without retraining."""
    if role.lower() != "admin":
        raise HLRValidationError("Unauthorized: Only users with 'admin' role can execute model rollbacks")

    target = uow.models.get(to_model_id)
    if target is None:
        raise HLRValidationError(f"Target rollback model '{to_model_id}' not found in registry")

    # Set active in repository
    activated_record = uow.models.set_active(to_model_id)

    # Mark states stale
    all_states = uow.concept_states.list_by_student(None)
    for cs in all_states:
        cs.model_version = f"{activated_record.id}:stale"
        uow.concept_states.upsert(cs)

    GLOBAL_REGISTRY.invalidate_cache()

    AUDIT_LOGS.append(AuditLogEntry(
        action="rollback",
        model_id=to_model_id,
        approver=approver,
        timestamp_utc=datetime.now(timezone.utc).isoformat(),
        reasons=[f"Administrative rollback to {to_model_id}"]
    ))

    return activated_record
