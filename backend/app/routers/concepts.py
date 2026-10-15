from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.models import Concept, ConceptState, Subject, TrainingRecord
from app.schemas.schemas import ConceptResponse, ConceptCurveResponse, CurvePoint, HistoryPoint
from app.services.hlr import recall_prob, next_review_days, generate_forgetting_curve_points

router = APIRouter(prefix="/api/concepts", tags=["concepts"])


@router.get("", response_model=list[ConceptResponse])
def get_concepts(subject_id: int | None = None, user_id: int = 1, db: Session = Depends(get_db)):
    query = db.query(Concept).join(Subject)
    if subject_id:
        query = query.filter(Concept.subject_id == subject_id)
    concepts = query.all()

    now = datetime.now(timezone.utc)
    results = []
    for c in concepts:
        state = db.query(ConceptState).filter(
            ConceptState.user_id == user_id,
            ConceptState.concept_id == c.id
        ).first()

        h = state.h_hat if state else 2.0
        c_correct = state.total_correct if state else 0
        c_incorrect = state.total_incorrect if state else 0
        
        if state and state.last_practiced_at:
            lp = state.last_practiced_at
            if lp.tzinfo is None:
                lp = lp.replace(tzinfo=timezone.utc)
            delta = (now - lp).total_seconds() / 86400.0
            p = recall_prob(h, delta)
        else:
            p = 0.5

        results.append(
            ConceptResponse(
                id=c.id,
                subject_id=c.subject_id,
                topic_id=c.topic_id,
                name=c.name,
                description=c.description,
                created_at=c.created_at,
                h_hat=round(h, 2),
                p_hat_current=round(p, 3),
                total_correct=c_correct,
                total_incorrect=c_incorrect,
                next_review_at=state.next_review_at if state else None,
            )
        )
    return results


@router.get("/{concept_id}/curve", response_model=ConceptCurveResponse)
def get_concept_curve(concept_id: int, user_id: int = 1, db: Session = Depends(get_db)):
    concept = db.query(Concept).filter(Concept.id == concept_id).first()
    if not concept:
        raise HTTPException(status_code=404, detail="Concept not found")

    state = db.query(ConceptState).filter(
        ConceptState.user_id == user_id,
        ConceptState.concept_id == concept_id
    ).first()

    now = datetime.now(timezone.utc)
    h = state.h_hat if (state and state.h_hat) else 2.0
    
    if state and state.last_practiced_at:
        lp = state.last_practiced_at
        if lp.tzinfo is None:
            lp = lp.replace(tzinfo=timezone.utc)
        delta_days = max(0.0, (now - lp).total_seconds() / 86400.0)
    else:
        delta_days = 0.0

    current_p = recall_prob(h, delta_days)
    threshold = 0.7
    review_window = next_review_days(h, threshold=threshold)

    # 1. Continuous decay points for chart
    raw_points = generate_forgetting_curve_points(h=h, threshold=threshold, num_points=35)
    curve_points = [
        CurvePoint(day=pt["day"], probability=pt["probability"], threshold=pt["threshold"])
        for pt in raw_points
    ]

    # 2. Historical practice records
    records = db.query(TrainingRecord).filter(
        TrainingRecord.user_id == user_id,
        TrainingRecord.concept_id == concept_id
    ).order_by(TrainingRecord.created_at.asc()).all()

    practice_history = [
        HistoryPoint(
            session_id=r.session_id,
            recorded_at=r.created_at,
            delta_days=round(r.delta_days, 2),
            observed_p=round(r.p, 3),
        )
        for r in records
    ]

    return ConceptCurveResponse(
        concept_id=concept.id,
        concept_name=concept.name,
        subject_name=concept.subject.name if concept.subject else "General",
        h_hat=round(h, 2),
        current_delta_days=round(delta_days, 2),
        current_p=round(current_p, 3),
        threshold=threshold,
        next_review_days=round(review_window, 2),
        curve_points=curve_points,
        practice_history=practice_history,
    )
