import sys
from typing import Any
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.schemas.schemas import PlanResponse
from app.services.scheduler import generate_study_plan

router = APIRouter(prefix="/api/plan", tags=["plan"])


@router.get("/today", response_model=PlanResponse)
def get_today_plan(user_id: int = 1, db: Session = Depends(get_db)):
    return generate_study_plan(db, user_id=user_id, days_count=1)


@router.get("/week")
def get_week_plan(user_id: int = 1, db: Session = Depends(get_db)) -> Any:
    main_mod = sys.modules.get("main")
    if main_mod and hasattr(main_mod, "get_week_plan"):
        return main_mod.get_week_plan(user_id=None, db=db)
    return generate_study_plan(db, user_id=user_id, days_count=7)
