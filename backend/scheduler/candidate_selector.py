"""
backend/scheduler/candidate_selector.py
Selects eligible due concepts and capped new concepts for study plan scheduling.
Does NOT import predictor or trainer (isolation invariant).
"""
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Sequence, List, Dict, Any, Optional, Tuple

@dataclass
class ConceptLearningState:
    concept_id: str
    student_id: str
    subject: str
    topic: str
    name: str
    difficulty: str
    recall_prob_now: float
    next_review_at: datetime
    is_new: bool
    half_life_days: float
    model_version: str

def select_due_candidates(
    states: Sequence[ConceptLearningState],
    window_end: datetime,
    target_student_id: Optional[str] = None,
    new_concept_cap: int = 2
) -> Tuple[List[ConceptLearningState], List[ConceptLearningState]]:
    """Selects concepts due for review (next_review_at <= window_end) and capped new concepts.
    
    Guarantees:
    - Multi-tenant safety: isolates target_student_id
    - Excludes future concepts (next_review_at > window_end)
    - Enforces new_concept_cap
    Returns (due_candidates, new_candidates).
    """
    due_list: List[ConceptLearningState] = []
    new_list: List[ConceptLearningState] = []

    for s in states:
        if target_student_id is not None and s.student_id != target_student_id:
            continue

        if s.is_new:
            new_list.append(s)
        else:
            # Check due window
            if s.next_review_at <= window_end:
                due_list.append(s)

    # Cap new concepts
    capped_new = new_list[:new_concept_cap]
    return due_list, capped_new
