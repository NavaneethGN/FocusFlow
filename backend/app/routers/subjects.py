import sys
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.models import Subject as DBSubject, Concept as DBConcept, Material as DBMaterial, UserSettings as DBUserSettings
from app.schemas.schemas import SubjectCreate, SubjectUpdate, SubjectDetail

router = APIRouter(prefix="/api/subjects", tags=["subjects"])


def _get_main():
    return sys.modules.get("main")


def _get_in_memory_subject_metrics(subject_name: str) -> Dict[str, Any]:
    """Helper to compute concepts count and avg p_hat from main in-memory store."""
    try:
        main = _get_main()
        if not main:
            return {"total_concepts": 0, "total_materials": 0, "due_concepts_count": 0, "weak_concepts_count": 0, "avg_p_hat": 0.0}
        concepts = [c for c in main.db_concepts.values() if c.get("subject", "").lower() == subject_name.lower()]
        materials = [m for m in main.db_materials if m.get("subject", "").lower() == subject_name.lower()]
        
        due = sum(1 for c in concepts if c.get("is_due", False))
        weak = sum(1 for c in concepts if c.get("p_hat", 1.0) < 0.65)
        avg_p = sum(c.get("p_hat", 0.0) for c in concepts) / len(concepts) if concepts else 0.0
        
        return {
            "total_concepts": len(concepts),
            "total_materials": len(materials),
            "due_concepts_count": due,
            "weak_concepts_count": weak,
            "avg_p_hat": round(avg_p, 3)
        }
    except Exception:
        return {
            "total_concepts": 0,
            "total_materials": 0,
            "due_concepts_count": 0,
            "weak_concepts_count": 0,
            "avg_p_hat": 0.0
        }


@router.get("", response_model=List[SubjectDetail])
def list_subjects(user_id: int = 1, db: Session = Depends(get_db)):
    """List all tracked subjects with their concepts counts, retention, and exam dates."""
    # Try fetching from DB first
    db_subs = db.query(DBSubject).filter(DBSubject.user_id == user_id).all()
    
    # Also get in-memory priorities and exam dates
    in_mem_priorities = {}
    in_mem_exam_dates = {}
    in_mem_subjects_seen = set()
    
    try:
        main = _get_main()
        if main:
            in_mem_priorities = getattr(main.db_settings, "subject_priorities", {})
            in_mem_exam_dates = getattr(main.db_settings, "exam_dates", {})
            for c in main.db_concepts.values():
                in_mem_subjects_seen.add(c.get("subject"))
    except Exception:
        pass

    results: List[SubjectDetail] = []
    seen_names = set()

    for s in db_subs:
        metrics = _get_in_memory_subject_metrics(s.name)
        # Use DB metrics if available and concepts exist in DB
        db_concept_count = len(s.concepts) if s.concepts else 0
        db_mat_count = len(s.materials) if s.materials else 0
        total_concepts = max(metrics["total_concepts"], db_concept_count)
        total_materials = max(metrics["total_materials"], db_mat_count)
        
        results.append(SubjectDetail(
            id=s.id,
            name=s.name,
            color=s.color or "#4f46e5",
            priority_weight=in_mem_priorities.get(s.name, s.priority_weight or 1.0),
            exam_date=in_mem_exam_dates.get(s.name),
            total_concepts=total_concepts,
            total_materials=total_materials,
            avg_p_hat=metrics["avg_p_hat"],
            due_concepts_count=metrics["due_concepts_count"],
            weak_concepts_count=metrics["weak_concepts_count"]
        ))
        seen_names.add(s.name.lower())

    # Include any subjects currently tracked in in-memory settings but not yet in DB table
    palette = ["#3b82f6", "#10b981", "#8b5cf6", "#f59e0b", "#ec4899", "#06b6d4"]
    for idx, (name, prio) in enumerate(in_mem_priorities.items()):
        if name.lower() not in seen_names:
            metrics = _get_in_memory_subject_metrics(name)
            results.append(SubjectDetail(
                id=f"subj-{idx+10}",
                name=name,
                color=palette[idx % len(palette)],
                priority_weight=prio,
                exam_date=in_mem_exam_dates.get(name),
                total_concepts=metrics["total_concepts"],
                total_materials=metrics["total_materials"],
                avg_p_hat=metrics["avg_p_hat"],
                due_concepts_count=metrics["due_concepts_count"],
                weak_concepts_count=metrics["weak_concepts_count"]
            ))
            seen_names.add(name.lower())

    for idx, name in enumerate(in_mem_subjects_seen):
        if name and name.lower() not in seen_names:
            metrics = _get_in_memory_subject_metrics(name)
            results.append(SubjectDetail(
                id=f"subj-concept-{idx+1}",
                name=name,
                color=palette[(len(results)) % len(palette)],
                priority_weight=1.0,
                exam_date=(datetime.now(timezone.utc) + timedelta(days=21)).strftime("%Y-%m-%d"),
                total_concepts=metrics["total_concepts"],
                total_materials=metrics["total_materials"],
                avg_p_hat=metrics["avg_p_hat"],
                due_concepts_count=metrics["due_concepts_count"],
                weak_concepts_count=metrics["weak_concepts_count"]
            ))
            seen_names.add(name.lower())

    return results


@router.post("", response_model=SubjectDetail)
def create_subject(req: SubjectCreate, user_id: int = 1, db: Session = Depends(get_db)):
    """Creates a new subject, initializing its priority, exam date, and persistence."""
    cleaned_name = req.name.strip()
    if not cleaned_name:
        raise HTTPException(status_code=400, detail="Subject name cannot be empty")

    default_exam = req.exam_date or (datetime.now(timezone.utc) + timedelta(days=21)).strftime("%Y-%m-%d")

    # 1. Update in-memory state in main.py
    try:
        main = _get_main()
        if main:
            main.db_settings.subject_priorities[cleaned_name] = req.priority_weight
            main.db_settings.exam_dates[cleaned_name] = default_exam
    except Exception:
        pass

    # 2. Persist in database
    existing = db.query(DBSubject).filter(
        DBSubject.user_id == user_id,
        DBSubject.name.ilike(cleaned_name)
    ).first()

    if existing:
        existing.color = req.color or existing.color
        existing.priority_weight = req.priority_weight
        db.commit()
        db.refresh(existing)
        target_id = existing.id
    else:
        new_sub = DBSubject(
            user_id=user_id,
            name=cleaned_name,
            color=req.color or "#4f46e5",
            priority_weight=req.priority_weight
        )
        db.add(new_sub)
        db.commit()
        db.refresh(new_sub)
        target_id = new_sub.id

    return SubjectDetail(
        id=target_id,
        name=cleaned_name,
        color=req.color or "#4f46e5",
        priority_weight=req.priority_weight,
        exam_date=default_exam,
        total_concepts=0,
        total_materials=0,
        avg_p_hat=1.0,
        due_concepts_count=0,
        weak_concepts_count=0
    )


@router.put("/{subject_identifier}", response_model=SubjectDetail)
def update_subject(subject_identifier: str, req: SubjectUpdate, user_id: int = 1, db: Session = Depends(get_db)):
    """Updates subject metadata like priority weight, color, or exam date."""
    target = None
    if subject_identifier.isdigit():
        target = db.query(DBSubject).filter(DBSubject.id == int(subject_identifier)).first()
    if not target:
        target = db.query(DBSubject).filter(
            DBSubject.user_id == user_id,
            DBSubject.name.ilike(subject_identifier)
        ).first()

    sub_name = target.name if target else subject_identifier

    try:
        main = _get_main()
        if main:
            if req.priority_weight is not None:
                main.db_settings.subject_priorities[sub_name] = req.priority_weight
            if req.exam_date is not None:
                main.db_settings.exam_dates[sub_name] = req.exam_date
            if req.name and req.name.strip() and req.name.strip() != sub_name:
                new_n = req.name.strip()
                prio = main.db_settings.subject_priorities.pop(sub_name, 1.0)
                ex = main.db_settings.exam_dates.pop(sub_name, None)
                main.db_settings.subject_priorities[new_n] = req.priority_weight or prio
                if ex or req.exam_date:
                    main.db_settings.exam_dates[new_n] = req.exam_date or ex
                for c in main.db_concepts.values():
                    if c.get("subject", "").lower() == sub_name.lower():
                        c["subject"] = new_n
                sub_name = new_n
    except Exception:
        pass

    if target:
        if req.name and req.name.strip():
            target.name = req.name.strip()
        if req.color:
            target.color = req.color
        if req.priority_weight is not None:
            target.priority_weight = req.priority_weight
        db.commit()
        db.refresh(target)

    metrics = _get_in_memory_subject_metrics(sub_name)
    color = target.color if target else (req.color or "#4f46e5")
    prio = req.priority_weight if req.priority_weight is not None else (target.priority_weight if target else 1.0)
    
    exam_date = req.exam_date
    if not exam_date:
        try:
            main = _get_main()
            if main:
                exam_date = main.db_settings.exam_dates.get(sub_name)
        except Exception:
            pass

    return SubjectDetail(
        id=target.id if target else subject_identifier,
        name=sub_name,
        color=color,
        priority_weight=prio,
        exam_date=exam_date,
        total_concepts=metrics["total_concepts"],
        total_materials=metrics["total_materials"],
        avg_p_hat=metrics["avg_p_hat"],
        due_concepts_count=metrics["due_concepts_count"],
        weak_concepts_count=metrics["weak_concepts_count"]
    )


@router.delete("/{subject_identifier}")
def delete_subject(subject_identifier: str, user_id: int = 1, db: Session = Depends(get_db)):
    """Deletes a subject from tracking."""
    target = None
    if subject_identifier.isdigit():
        target = db.query(DBSubject).filter(DBSubject.id == int(subject_identifier)).first()
    if not target:
        target = db.query(DBSubject).filter(
            DBSubject.user_id == user_id,
            DBSubject.name.ilike(subject_identifier)
        ).first()

    name_to_remove = target.name if target else subject_identifier

    # Remove from in-memory state
    try:
        main = _get_main()
        if main:
            main.db_settings.subject_priorities.pop(name_to_remove, None)
            main.db_settings.exam_dates.pop(name_to_remove, None)
    except Exception:
        pass

    # Remove from DB if exists
    if target:
        db.delete(target)
        db.commit()

    return {"success": True, "deleted_subject": name_to_remove}
