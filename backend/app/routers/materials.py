from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.models import Material, Concept, Question, Subject, ConceptState
from app.schemas.schemas import MaterialUploadRequest, MaterialUploadResponse, ConceptResponse
from app.services.quiz_gen import generate_concepts_and_questions

router = APIRouter(prefix="/api/materials", tags=["materials"])


@router.post("", response_model=MaterialUploadResponse)
async def upload_material(request: MaterialUploadRequest, db: Session = Depends(get_db)):
    subject = None
    if request.subject_id:
        subject = db.query(Subject).filter(Subject.id == request.subject_id).first()
    if not subject and request.subject:
        subject = db.query(Subject).filter(Subject.name == request.subject).first()
    if not subject:
        # Create default subject if it doesn't exist yet
        subject = Subject(user_id=1, name=request.subject or "General Study", color="#4f46e5")
        db.add(subject)
        db.commit()
        db.refresh(subject)

    # Save material
    material = Material(
        subject_id=subject.id,
        title=request.title,
        content=request.content,
    )
    db.add(material)
    db.commit()
    db.refresh(material)

    # Generate concepts and questions
    generated_items = await generate_concepts_and_questions(request.title, request.content)
    
    created_concepts = []
    created_questions = []
    total_questions = 0

    for item in generated_items:
        concept = Concept(
            subject_id=subject.id,
            name=item["name"],
            description=item.get("description", ""),
        )
        db.add(concept)
        db.commit()
        db.refresh(concept)

        # Initialize default ConceptState for user 1
        state = ConceptState(
            user_id=1,
            concept_id=concept.id,
            total_correct=0,
            total_incorrect=0,
            h_hat=2.0,
            p_hat_cached=0.5,
        )
        db.add(state)

        for q in item.get("questions", []):
            question = Question(
                concept_id=concept.id,
                text=q["text"],
                options=q["options"],
                answer_index=q.get("answer_index", 0),
                explanation=q.get("explanation"),
                status="approved",
            )
            db.add(question)
            db.commit()
            db.refresh(question)
            created_questions.append({
                "id": f"q-{question.id}",
                "question_id": question.id,
                "concept_id": str(concept.id),
                "concept_name": concept.name,
                "subject": subject.name,
                "text": question.text,
                "options": question.options,
                "answer_index": question.answer_index,
                "explanation": question.explanation,
                "status": question.status,
            })
            total_questions += 1

        db.commit()
        created_concepts.append(
            ConceptResponse(
                id=concept.id,
                subject_id=subject.id,
                topic_id=None,
                name=concept.name,
                description=concept.description,
                created_at=concept.created_at,
                h_hat=2.0,
                p_hat_current=0.5,
                half_life_days=2.0,
                p_hat=0.5,
                delta_days=0.0,
                is_due=True,
                subject=subject.name,
                topic=concept.name,
                total_correct=0,
                total_incorrect=0,
            )
        )

    return MaterialUploadResponse(
        material_id=material.id,
        subject_id=subject.id,
        title=material.title,
        concepts_generated=len(created_concepts),
        questions_generated=total_questions,
        concepts=created_concepts,
        concept=created_concepts[0] if created_concepts else None,
        generated_questions=created_questions,
    )
