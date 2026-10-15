"""
backend/scheduler/priority.py
Calculates subject urgency weights and orders concepts by memory strength.
Does NOT import predictor or trainer (isolation invariant).
"""
from datetime import datetime, timezone
from typing import Sequence, List, Dict, Any, Optional
from .candidate_selector import ConceptLearningState

def compute_exam_boost(exam_date: Optional[str], now: datetime) -> float:
    """Computes multiplier boost for subjects with approaching exam dates."""
    if not exam_date:
        return 1.0
    try:
        exam_dt = datetime.fromisoformat(exam_date)
        if exam_dt.tzinfo is None:
            exam_dt = exam_dt.replace(tzinfo=timezone.utc)
        days_left = (exam_dt - now).total_seconds() / 86400.0
        if days_left <= 0:
            return 2.5
        elif days_left < 30:
            return 1.0 + ((30.0 - days_left) / 20.0)
        return 1.0
    except Exception:
        return 1.0

def compute_subject_weights(
    concepts_by_subject: Dict[str, List[ConceptLearningState]],
    subject_priorities: Dict[str, float],
    exam_dates: Dict[str, str],
    now: datetime
) -> Dict[str, float]:
    """Computes normalized scheduling weights across subjects.
    
    Guarantees:
    - Subject fairness: a subject with 0 due/review concepts receives 0.0 weight.
    - Exam boost: approaching exam dates monotonically increase subject urgency.
    """
    weights: Dict[str, float] = {}

    for subj, concepts in concepts_by_subject.items():
        if len(concepts) == 0:
            weights[subj] = 0.0
            continue

        avg_p = sum(c.recall_prob_now for c in concepts) / len(concepts)
        priority_mult = subject_priorities.get(subj, 1.0)
        exam_boost = compute_exam_boost(exam_dates.get(subj), now)

        # Base urgency: higher when recall is lower
        urgency = priority_mult * exam_boost * ((1.0 - avg_p) * 2.0 + 0.5)
        weights[subj] = max(0.01, urgency)

    return weights

def rank_concepts_within_subject(
    concepts: Sequence[ConceptLearningState]
) -> List[ConceptLearningState]:
    """Orders concepts strictly by lowest recall probability first."""
    return sorted(concepts, key=lambda c: c.recall_prob_now)
