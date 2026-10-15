from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from app.models.models import Concept, ConceptState, Subject, UserSettings
from app.services.hlr import recall_prob, next_review_days, DEFAULT_LAUNCH_THETA
from app.schemas.schemas import PlanResponse, DailyPlan, PlanConceptItem


def get_concept_current_p(state: ConceptState | None, now: datetime) -> tuple[float, float, float]:
    """Returns (current_p, delta_days, h_hat) for a concept state."""
    if state is None or state.last_practiced_at is None:
        # Unseen / fresh concept: 0 delta, baseline initial p = 0.5
        h = state.h_hat if state else 2.0
        return 0.5, 0.0, h
    
    last_practiced = state.last_practiced_at
    if last_practiced.tzinfo is None:
        last_practiced = last_practiced.replace(tzinfo=timezone.utc)
        
    delta_days = max(0.0, (now - last_practiced).total_seconds() / 86400.0)
    h = state.h_hat or 2.0
    p = recall_prob(h, delta_days)
    return p, delta_days, h


def generate_study_plan(db: Session, user_id: int, days_count: int = 1) -> PlanResponse:
    now = datetime.now(timezone.utc)

    # 1. Fetch user settings
    settings = db.query(UserSettings).filter(UserSettings.user_id == user_id).first()
    daily_budget = settings.daily_minutes if settings else 60
    subject_priorities = settings.subject_priorities if settings and settings.subject_priorities else {}

    # 2. Fetch all subjects and their concepts
    subjects = db.query(Subject).filter(Subject.user_id == user_id).all()
    if not subjects:
        # Default mock subject if empty
        return PlanResponse(
            generated_at=now,
            daily_budget_minutes=daily_budget,
            plan=[
                DailyPlan(
                    date_str=(now + timedelta(days=d)).strftime("%Y-%m-%d"),
                    day_name=(now + timedelta(days=d)).strftime("%A"),
                    total_minutes=0,
                    concepts=[],
                )
                for d in range(days_count)
            ],
        )

    # Pre-fetch all concepts and their states for this user
    all_concepts = db.query(Concept).join(Subject).filter(Subject.user_id == user_id).all()
    concept_states = {
        cs.concept_id: cs
        for cs in db.query(ConceptState).filter(ConceptState.user_id == user_id).all()
    }

    # Evaluate each concept
    evaluated_concepts: List[Dict[str, Any]] = []
    for concept in all_concepts:
        state = concept_states.get(concept.id)
        p, delta_days, h = get_concept_current_p(state, now)
        is_fresh = (state is None or state.last_practiced_at is None)
        
        if is_fresh:
            status = "fresh"
        elif p < 0.5:
            status = "critical"
        elif p < 0.7:
            status = "due"
        else:
            status = "learning"

        evaluated_concepts.append({
            "concept": concept,
            "subject": concept.subject,
            "p": p,
            "delta_days": delta_days,
            "h": h,
            "status": status,
            "is_fresh": is_fresh,
        })

    # Sort candidates by recall probability (lowest p first)
    evaluated_concepts.sort(key=lambda item: item["p"])

    # 3. Build days plan
    daily_plans: List[DailyPlan] = []
    concepts_pool = list(evaluated_concepts)
    minutes_per_concept = 15

    for day_offset in range(days_count):
        current_date = now + timedelta(days=day_offset)
        day_date_str = current_date.strftime("%Y-%m-%d")
        day_name = current_date.strftime("%A")

        scheduled_items: List[PlanConceptItem] = []
        spent_minutes = 0

        # Prioritize concepts that are due or low p
        remaining_pool = []
        for item in concepts_pool:
            if spent_minutes + minutes_per_concept <= daily_budget:
                c = item["concept"]
                s = item["subject"]
                scheduled_items.append(
                    PlanConceptItem(
                        concept_id=c.id,
                        concept_name=c.name,
                        subject_name=s.name,
                        subject_color=s.color or "#4f46e5",
                        h_hat=round(item["h"], 2),
                        current_p=round(item["p"], 3),
                        due_status=item["status"],
                        allocated_minutes=minutes_per_concept,
                    )
                )
                spent_minutes += minutes_per_concept
            else:
                remaining_pool.append(item)

        daily_plans.append(
            DailyPlan(
                date_str=day_date_str,
                day_name=day_name,
                total_minutes=spent_minutes,
                concepts=scheduled_items,
            )
        )
        concepts_pool = remaining_pool

    # Build blocks for frontend compatibility
    first_day_concepts = daily_plans[0].concepts if daily_plans else []
    blocks_by_subj: Dict[str, list] = {}
    for ci in first_day_concepts:
        if ci.subject_name not in blocks_by_subj:
            blocks_by_subj[ci.subject_name] = []
        blocks_by_subj[ci.subject_name].append({
            "id": ci.concept_id,
            "name": ci.concept_name,
            "subject": ci.subject_name,
            "p_hat": ci.current_p,
            "half_life_days": ci.h_hat,
            "allocated_minutes": ci.allocated_minutes
        })

    blocks = [
        {
            "id": f"block-{s.lower().replace(' ', '-')}",
            "subject": s,
            "allocated_minutes": sum(c["allocated_minutes"] for c in clist),
            "estimated_questions": len(clist) * 2,
            "avg_p_hat": round(sum(c["p_hat"] for c in clist) / len(clist), 3) if clist else 0.5,
            "concepts": clist,
        }
        for s, clist in blocks_by_subj.items()
    ]

    total_sched = sum(b["allocated_minutes"] for b in blocks)
    due_total = sum(1 for c in evaluated_concepts if c["status"] in ("critical", "due"))

    return PlanResponse(
        generated_at=now,
        daily_budget_minutes=daily_budget,
        plan=daily_plans,
        date=now.strftime("%Y-%m-%d"),
        daily_minutes_goal=daily_budget,
        total_scheduled_minutes=total_sched,
        due_concepts_total=due_total,
        blocks=blocks,
    )
