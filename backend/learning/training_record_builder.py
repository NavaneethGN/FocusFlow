"""
backend/learning/training_record_builder.py
Constructs leak-free training records for Half-Life Regression.

ASSUMPTIONS:
1. Delta is computed from the previous session completion timestamp to the current
   session completion timestamp.
2. The observation label is the session accuracy fraction (correct / total scored answers)
   with n_answers preserved to enable weighted regression (Settles & Meeder 2016).
3. x_before is extracted from counts_before BEFORE applying the session's new outcomes,
   preventing target leakage.
"""
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List

from hlr.features import ConceptCounts, extract_features
from hlr.updater import ModelArtifact
from repositories.base import TrainingRecord
from .session_aggregator import ConceptSessionStats

def build_training_record(
    student_id: str,
    concept_id: str,
    session_id: str,
    stats: ConceptSessionStats,
    counts_before: ConceptCounts,
    last_practiced_at: datetime,
    completed_at: datetime,
    model: ModelArtifact,
    context_before: Optional[Dict[str, Any]] = None
) -> TrainingRecord:
    """Builds an immutable TrainingRecord representing practice recall after elapsed delta."""
    if last_practiced_at.tzinfo is None:
        last_practiced_at = last_practiced_at.replace(tzinfo=timezone.utc)
    if completed_at.tzinfo is None:
        completed_at = completed_at.replace(tzinfo=timezone.utc)

    delta_seconds = max(1.0, (completed_at - last_practiced_at).total_seconds())
    delta_days = delta_seconds / 86400.0

    # Strictly extract features before incrementing counts
    x_before = extract_features(counts_before, model.feature_spec, context_before)

    return TrainingRecord(
        student_id=student_id,
        concept_id=concept_id,
        session_id=session_id,
        p_observed=stats.p_session,
        n_answers=stats.total,
        delta_days=delta_days,
        counts_before={
            "n_right": counts_before.n_right,
            "n_wrong": counts_before.n_wrong
        },
        x_before=x_before,
        feature_spec_name=model.feature_spec.name,
        model_version=model.name,
        source_event_ids=list(stats.event_ids),
        created_at=completed_at,
        label_definition_version="1.0"
    )
