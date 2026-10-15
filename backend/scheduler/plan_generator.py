"""
backend/scheduler/plan_generator.py
Generates daily and weekly study plans adhering to strict time budgets, subject fairness,
overflow carryover, and response shape preservation.
Does NOT import predictor or trainer (isolation invariant).
"""
from dataclasses import asdict
from datetime import datetime, timezone, timedelta
import math
from typing import Sequence, List, Dict, Any, Optional, Tuple

from .candidate_selector import ConceptLearningState, select_due_candidates
from .priority import compute_subject_weights, rank_concepts_within_subject

POLICY_VERSION = "2.0-hlr-capacity-constrained"

def get_concept_learning_state(
    student_id: str,
    concept_ids: Optional[Sequence[str]] = None,
    raw_concepts: Optional[Dict[str, Any]] = None,
    now: Optional[datetime] = None
) -> List[ConceptLearningState]:
    """Helper reading concept learning states without recomputing half-lives."""
    if raw_concepts is None:
        return []

    curr_now = now or datetime.now(timezone.utc)
    results: List[ConceptLearningState] = []

    for cid, c in raw_concepts.items():
        if concept_ids and cid not in concept_ids:
            continue

        c_student = c.get("student_id", student_id)
        if c_student != student_id:
            continue

        nr = c.get("n_right", 0)
        nw = c.get("n_wrong", 0)
        is_new_concept = (nr + nw == 0)

        next_rev_str = c.get("next_review_at")
        if next_rev_str:
            try:
                next_rev_dt = datetime.fromisoformat(next_rev_str)
                if next_rev_dt.tzinfo is None:
                    next_rev_dt = next_rev_dt.replace(tzinfo=timezone.utc)
            except Exception:
                next_rev_dt = curr_now
        else:
            next_rev_dt = curr_now

        p_hat = float(c.get("p_hat", 0.95))
        h_days = float(c.get("half_life_days", 1.0))
        m_version = str(c.get("model_version", "hlr_v0_fixed"))

        results.append(ConceptLearningState(
            concept_id=cid,
            student_id=student_id,
            subject=c.get("subject", "General"),
            topic=c.get("topic", "General"),
            name=c.get("name", cid),
            difficulty=c.get("difficulty", "Medium"),
            recall_prob_now=p_hat,
            next_review_at=next_rev_dt,
            is_new=is_new_concept,
            half_life_days=h_days,
            model_version=m_version
        ))

    return results

def generate_today_plan(
    states: Sequence[ConceptLearningState],
    daily_minutes: int,
    subject_priorities: Dict[str, float],
    exam_dates: Dict[str, str],
    now: datetime,
    active_model_version: str = "hlr_v0_fixed",
    student_id: Optional[str] = None,
    questions_store: Optional[List[Dict[str, Any]]] = None
) -> Tuple[Dict[str, Any], List[ConceptLearningState]]:
    """Generates day 1 study plan constrained to daily_minutes budget.
    
    Returns (plan_dict, overflow_concepts).
    """
    due_concepts, new_concepts = select_due_candidates(
        states=states,
        window_end=now + timedelta(hours=24),
        target_student_id=student_id,
        new_concept_cap=2
    )

    all_eligible = due_concepts + new_concepts
    # Group by subject
    by_subject: Dict[str, List[ConceptLearningState]] = {}
    for c in all_eligible:
        by_subject.setdefault(c.subject, []).append(c)

    # Sort each subject's concepts: lowest recall probability first
    for subj in by_subject:
        by_subject[subj] = rank_concepts_within_subject(by_subject[subj])

    subj_weights = compute_subject_weights(by_subject, subject_priorities, exam_dates, now)
    total_weight = sum(subj_weights.values())

    blocks: List[Dict[str, Any]] = []
    total_scheduled_minutes = 0
    overflow_concepts: List[ConceptLearningState] = []

    # Subjects with non-zero weight
    active_subjects = [s for s, w in subj_weights.items() if w > 0.0]

    for subj in active_subjects:
        cand_list = by_subject[subj]
        if not cand_list:
            continue

        w = subj_weights[subj]
        raw_alloc = (w / total_weight) * daily_minutes if total_weight > 0 else (daily_minutes / len(active_subjects))
        # Ensure planned minutes never exceed daily_minutes
        remaining_budget = max(0, daily_minutes - total_scheduled_minutes)
        if remaining_budget <= 0:
            overflow_concepts.extend(cand_list)
            continue

        alloc_mins = min(remaining_budget, max(10, round(raw_alloc / 5.0) * 5))
        if alloc_mins == 0:
            overflow_concepts.extend(cand_list)
            continue

        # ~7 minutes per concept review
        max_concepts = max(1, alloc_mins // 7)
        accepted_concepts = cand_list[:max_concepts]
        overflow_concepts.extend(cand_list[max_concepts:])

        total_scheduled_minutes += alloc_mins

        # Format concepts matching legacy API snapshot
        concepts_out = []
        for ac in accepted_concepts:
            concepts_out.append({
                "id": ac.concept_id,
                "name": ac.name,
                "subject": ac.subject,
                "topic": ac.topic,
                "difficulty": ac.difficulty,
                "half_life_days": ac.half_life_days,
                "p_hat": round(ac.recall_prob_now, 4),
                "next_review_at": ac.next_review_at.isoformat(),
                "is_due": True
            })

        q_count = 4
        if questions_store:
            q_count = len([q for q in questions_store if any(q.get("concept_id") == ac.concept_id for ac in accepted_concepts)]) or 4

        avg_p = sum(ac.recall_prob_now for ac in accepted_concepts) / len(accepted_concepts)
        blocks.append({
            "id": f"block-{subj.lower().replace(' ', '-')}",
            "subject": subj,
            "allocated_minutes": alloc_mins,
            "estimated_questions": max(3, min(10, q_count)),
            "avg_p_hat": round(avg_p, 3),
            "concepts": concepts_out,
            "status": "ready"
        })

    blocks.sort(key=lambda b: b["avg_p_hat"])

    plan_response = {
        "date": now.strftime("%Y-%m-%d"),
        "daily_minutes_goal": daily_minutes,
        "total_scheduled_minutes": total_scheduled_minutes,
        "due_concepts_total": len(due_concepts),
        "blocks": blocks,
        "scheduler_algorithm": "HLR Weighted Memory Gradient Optimization",
        "policy_version": POLICY_VERSION,
        "active_model_version": active_model_version
    }
    return plan_response, overflow_concepts

def generate_week_plan(
    states: Sequence[ConceptLearningState],
    daily_minutes: int,
    subject_priorities: Dict[str, float],
    exam_dates: Dict[str, str],
    now: datetime,
    retention_threshold: float = 0.70,
    active_model_version: str = "hlr_v0_fixed"
) -> Dict[str, Any]:
    """Generates 7-day adaptive forecast with overflow carried over to next days."""
    days = []
    # Start with day 0 plan
    today_plan, overflow = generate_today_plan(
        states=states,
        daily_minutes=daily_minutes,
        subject_priorities=subject_priorities,
        exam_dates=exam_dates,
        now=now,
        active_model_version=active_model_version
    )

    day_0_concepts = []
    for b in today_plan["blocks"]:
        for c in b["concepts"]:
            day_0_concepts.append({"name": c["name"], "subject": c["subject"], "p_hat": c["p_hat"]})

    days.append({
        "day_index": 0,
        "date": now.strftime("%Y-%m-%d"),
        "weekday": now.strftime("%A"),
        "planned_minutes": today_plan["total_scheduled_minutes"],
        "due_count": today_plan["due_concepts_total"],
        "concepts": day_0_concepts[:3]
    })

    carried_overflow = list(overflow)

    for i in range(1, 7):
        day_date = now + timedelta(days=i)
        # Any concepts whose next_review_at falls on or before this day
        newly_due = [s for s in states if s.next_review_at <= day_date and not s.is_new]
        # Combine with carried overflow from previous day
        day_pool = carried_overflow + [c for c in newly_due if c not in carried_overflow]

        p_mins = daily_minutes if i < 5 else max(25, daily_minutes - 15)
        # Pick top concepts
        day_concepts_out = [{"name": c.name, "subject": c.subject, "p_hat": round(c.recall_prob_now, 3)} for c in day_pool]

        # Carry over excess if pool exceeds day capacity
        max_c = p_mins // 7
        carried_overflow = day_pool[max_c:] if len(day_pool) > max_c else []

        days.append({
            "day_index": i,
            "date": day_date.strftime("%Y-%m-%d"),
            "weekday": day_date.strftime("%A"),
            "planned_minutes": p_mins,
            "due_count": len(day_pool),
            "concepts": day_concepts_out[:3]
        })

    return {
        "week_start": now.strftime("%Y-%m-%d"),
        "days": days,
        "policy_version": POLICY_VERSION,
        "active_model_version": active_model_version
    }
