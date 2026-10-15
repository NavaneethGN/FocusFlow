from datetime import datetime, timezone
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.models import Subject, Concept, ConceptState
from app.schemas.schemas import DashboardResponse, SubjectSummary, ConceptResponse
from app.services.hlr import recall_prob

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("", response_model=DashboardResponse)
def get_dashboard(user_id: int = 1, db: Session = Depends(get_db)):
    now = datetime.now(timezone.utc)
    subjects = db.query(Subject).filter(Subject.user_id == user_id).all()

    subject_summaries = []
    all_due_concepts: list[ConceptResponse] = []
    all_p_hats = []

    for subj in subjects:
        concepts = db.query(Concept).filter(Concept.subject_id == subj.id).all()
        subj_p_hats = []
        due_count = 0
        weak_count = 0

        for c in concepts:
            state = db.query(ConceptState).filter(
                ConceptState.user_id == user_id,
                ConceptState.concept_id == c.id
            ).first()

            h = state.h_hat if state else 2.0
            if state and state.last_practiced_at:
                lp = state.last_practiced_at
                if lp.tzinfo is None:
                    lp = lp.replace(tzinfo=timezone.utc)
                delta = max(0.0, (now - lp).total_seconds() / 86400.0)
                p = recall_prob(h, delta)
            else:
                p = 0.5  # Fresh/unlearned default

            subj_p_hats.append(p)
            all_p_hats.append(p)

            if p < 0.6:
                weak_count += 1
            if p < 0.7:
                due_count += 1
                all_due_concepts.append(
                    ConceptResponse(
                        id=c.id,
                        subject_id=c.subject_id,
                        topic_id=c.topic_id,
                        name=c.name,
                        description=c.description,
                        created_at=c.created_at,
                        h_hat=round(h, 2),
                        p_hat_current=round(p, 3),
                        total_correct=state.total_correct if state else 0,
                        total_incorrect=state.total_incorrect if state else 0,
                        next_review_at=state.next_review_at if state else None,
                    )
                )

        avg_p = sum(subj_p_hats) / len(subj_p_hats) if subj_p_hats else 0.5
        subject_summaries.append(
            SubjectSummary(
                subject_id=subj.id,
                name=subj.name,
                color=subj.color or "#4f46e5",
                total_concepts=len(concepts),
                avg_p_hat=round(avg_p, 3),
                due_concepts_count=due_count,
                weak_concepts_count=weak_count,
            )
        )

    overall_retention = sum(all_p_hats) / len(all_p_hats) if all_p_hats else 0.75

    # Sort due concepts by lowest recall probability first
    all_due_concepts.sort(key=lambda item: item.p_hat_current or 1.0)
    weak_count_total = sum(s.weak_concepts_count for s in subject_summaries)

    return DashboardResponse(
        user_id=user_id,
        overall_retention=round(overall_retention, 3),
        total_due_concepts=len(all_due_concepts),
        subjects=subject_summaries,
        due_concepts=all_due_concepts[:10],
        overall_retention_score=round(overall_retention * 100, 1),
        total_concepts=len(all_p_hats),
        due_concepts_count=len(all_due_concepts),
        weak_concepts_count=weak_count_total,
        daily_study_goal_minutes=60,
        minutes_studied_today=32,
        streak_days=8,
        retention_threshold=0.70,
        weakest_concepts=all_due_concepts[:4],
    )
