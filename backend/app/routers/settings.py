from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.models import UserSettings, User
from app.schemas.schemas import SettingsUpdateRequest, SettingsResponse

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("", response_model=SettingsResponse)
def get_settings(user_id: int = 1, db: Session = Depends(get_db)):
    settings = db.query(UserSettings).filter(UserSettings.user_id == user_id).first()
    if not settings:
        # Create default
        settings = UserSettings(
            user_id=user_id,
            daily_minutes=60,
            subject_priorities={},
            exam_dates={},
        )
        db.add(settings)
        db.commit()
        db.refresh(settings)

    return SettingsResponse(
        user_id=settings.user_id,
        daily_minutes=settings.daily_minutes,
        subject_priorities=settings.subject_priorities or {},
        exam_dates=settings.exam_dates or {},
    )


@router.put("", response_model=SettingsResponse)
def update_settings(request: SettingsUpdateRequest, user_id: int = 1, db: Session = Depends(get_db)):
    settings = db.query(UserSettings).filter(UserSettings.user_id == user_id).first()
    if not settings:
        settings = UserSettings(user_id=user_id)
        db.add(settings)

    settings.daily_minutes = request.daily_minutes
    settings.subject_priorities = request.subject_priorities
    settings.exam_dates = request.exam_dates
    db.commit()
    db.refresh(settings)

    return SettingsResponse(
        user_id=settings.user_id,
        daily_minutes=settings.daily_minutes,
        subject_priorities=settings.subject_priorities or {},
        exam_dates=settings.exam_dates or {},
    )
