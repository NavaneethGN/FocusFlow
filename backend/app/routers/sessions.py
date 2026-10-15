from datetime import datetime, timezone
from collections import defaultdict
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.models import (
    Session as StudySession,
    Attempt,
    Question,
    ConceptState,
    TrainingRecord,
    ModelVersion,
)
from app.schemas.schemas import AnswerSubmitRequest, AnswerSubmitResponse, CompleteSessionResponse
from app.services.hlr import (
    DEFAULT_LAUNCH_THETA,
    DEFAULT_FEATURE_SPEC,
    compute_session_concept_update,
)

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


@router.post("/{session_id}/answers", response_model=AnswerSubmitResponse)
def submit_answer(session_id: int, request: AnswerSubmitRequest, db: Session = Depends(get_db)):
    # 1. Check idempotency by event_id
    existing_attempt = db.query(Attempt).filter(Attempt.event_id == request.event_id).first()
    if existing_attempt:
        question = db.query(Question).filter(Question.id == existing_attempt.question_id).first()
        return AnswerSubmitResponse(
            event_id=request.event_id,
            is_correct=existing_attempt.is_correct,
            correct_index=question.answer_index if question else 0,
            explanation=question.explanation if question else None,
            already_recorded=True,
        )

    # 2. Validate session and question
    session = db.query(StudySession).filter(StudySession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Study session not found")
    if session.is_completed:
        raise HTTPException(status_code=400, detail="Session is already completed")

    question = db.query(Question).filter(Question.id == request.question_id).first()
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")

    is_correct = (request.selected_index == question.answer_index)

    # 3. Save attempt (append-only)
    attempt = Attempt(
        session_id=session_id,
        user_id=session.user_id,
        question_id=question.id,
        concept_id=question.concept_id,
        event_id=request.event_id,
        selected_index=request.selected_index,
        is_correct=is_correct,
        answered_at=datetime.now(timezone.utc),
    )
    db.add(attempt)
    db.commit()

    return AnswerSubmitResponse(
        event_id=request.event_id,
        is_correct=is_correct,
        correct_index=question.answer_index,
        explanation=question.explanation,
        already_recorded=False,
    )


@router.post("/{session_id}/complete", response_model=CompleteSessionResponse)
def complete_session(session_id: int, db: Session = Depends(get_db)):
    session = db.query(StudySession).filter(StudySession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Study session not found")
    if session.is_completed:
        raise HTTPException(status_code=400, detail="Session already closed")

    now = datetime.now(timezone.utc)
    user_id = session.user_id

    # Get active model version or default
    active_model = db.query(ModelVersion).filter(ModelVersion.is_active == True).first()
    theta = active_model.theta if active_model else DEFAULT_LAUNCH_THETA
    feature_spec = active_model.feature_spec if active_model else DEFAULT_FEATURE_SPEC

    # Fetch attempts for this session
    attempts = db.query(Attempt).filter(Attempt.session_id == session_id).all()
    if not attempts:
        session.is_completed = True
        session.completed_at = now
        db.commit()
        return CompleteSessionResponse(
            session_id=session_id,
            total_attempts=0,
            total_correct=0,
            session_accuracy=0.0,
            concepts_updated=[],
            completed_at=now,
        )

    # Group attempts by concept_id
    concept_attempts = defaultdict(list)
    for att in attempts:
        concept_attempts[att.concept_id].append(att)

    total_session_correct = sum(1 for a in attempts if a.is_correct)
    total_session_attempts = len(attempts)
    session_accuracy = round(float(total_session_correct) / float(total_session_attempts), 3)

    concepts_updated_info = []

    # Process HLR update per concept
    for concept_id, att_list in concept_attempts.items():
        c_correct = sum(1 for a in att_list if a.is_correct)
        c_total = len(att_list)

        state = db.query(ConceptState).filter(
            ConceptState.user_id == user_id,
            ConceptState.concept_id == concept_id
        ).first()

        if not state:
            state = ConceptState(
                user_id=user_id,
                concept_id=concept_id,
                total_correct=0,
                total_incorrect=0,
                h_hat=2.0,
                p_hat_cached=0.5,
            )
            db.add(state)
            db.flush()

        update_result = compute_session_concept_update(
            correct_session=c_correct,
            total_session=c_total,
            last_practiced_at=state.last_practiced_at,
            current_correct_total=state.total_correct,
            current_incorrect_total=state.total_incorrect,
            theta=theta,
            feature_spec=feature_spec,
            threshold=0.7,
            now=now,
        )

        # 1. Save training record
        training_rec = TrainingRecord(
            user_id=user_id,
            concept_id=concept_id,
            session_id=session_id,
            p=update_result["p_observed"],
            delta_days=update_result["delta_days"],
            x_before=update_result["x_before"],
            created_at=now,
        )
        db.add(training_rec)

        # 2. Update concept_state
        state.total_correct = update_result["new_correct_total"]
        state.total_incorrect = update_result["new_incorrect_total"]
        state.last_practiced_at = now
        state.h_hat = update_result["h_hat"]
        state.p_hat_cached = update_result["p_hat_cached"]
        state.next_review_at = update_result["next_review_at"]
        state.updated_at = now

        concepts_updated_info.append({
            "concept_id": concept_id,
            "session_correct": c_correct,
            "session_total": c_total,
            "p_observed": round(update_result["p_observed"], 3),
            "delta_days": round(update_result["delta_days"], 2),
            "new_h_hat": round(update_result["h_hat"], 2),
            "next_review_at": update_result["next_review_at"].isoformat(),
        })

    # Close session
    session.is_completed = True
    session.completed_at = now
    db.commit()

    return CompleteSessionResponse(
        session_id=session_id,
        total_attempts=total_session_attempts,
        total_correct=total_session_correct,
        session_accuracy=session_accuracy,
        concepts_updated=concepts_updated_info,
        completed_at=now,
    )
