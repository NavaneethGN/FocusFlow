from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.models import Question, Concept, Session as StudySession, Subject, ConceptState
from app.schemas.schemas import QuestionResponse, StartQuizRequest, StartQuizResponse, QuizQuestionItem
from app.services.hlr import recall_prob

router = APIRouter(prefix="/api/quizzes", tags=["quizzes"])


@router.get("/questions", response_model=list[QuestionResponse])
def get_questions(concept_id: int | None = None, status: str | None = None, db: Session = Depends(get_db)):
    query = db.query(Question)
    if concept_id:
        query = query.filter(Question.concept_id == concept_id)
    if status:
        query = query.filter(Question.status == status)
    return query.all()


@router.post("/start", response_model=StartQuizResponse)
def start_quiz(request: StartQuizRequest, db: Session = Depends(get_db)):
    now = datetime.now(timezone.utc)
    user_id = request.user_id

    # Create new study session
    session = StudySession(
        user_id=user_id,
        subject_id=request.subject_id,
        is_completed=False,
        started_at=now,
    )
    db.add(session)
    db.commit()
    db.refresh(session)

    # Question selection logic:
    # 1. Filter by subject or concept IDs if provided
    query = db.query(Question).join(Concept)
    if request.subject_id:
        query = query.filter(Concept.subject_id == request.subject_id)
    if request.concept_ids:
        query = query.filter(Question.concept_id.in_(request.concept_ids))
    query = query.filter(Question.status == "approved")

    all_candidate_questions = query.all()
    if not all_candidate_questions:
        # Fallback: any approved question
        all_candidate_questions = db.query(Question).filter(Question.status == "approved").limit(request.limit).all()

    # Prioritize questions for concepts with the lowest recall probability p̂
    concept_states = {
        cs.concept_id: cs
        for cs in db.query(ConceptState).filter(ConceptState.user_id == user_id).all()
    }

    def score_question(q: Question) -> float:
        cs = concept_states.get(q.concept_id)
        if not cs or cs.last_practiced_at is None:
            return 0.4  # High priority for unseen
        lp = cs.last_practiced_at
        if lp.tzinfo is None:
            lp = lp.replace(tzinfo=timezone.utc)
        delta = (now - lp).total_seconds() / 86400.0
        return recall_prob(cs.h_hat, delta)

    sorted_questions = sorted(all_candidate_questions, key=score_question)[:request.limit]

    items = [
        QuizQuestionItem(
            question_id=q.id,
            concept_id=q.concept_id,
            concept_name=q.concept.name if q.concept else "General",
            text=q.text,
            options=q.options,
        )
        for q in sorted_questions
    ]

    return StartQuizResponse(
        session_id=session.id,
        user_id=user_id,
        subject_id=request.subject_id,
        questions=items,
    )
