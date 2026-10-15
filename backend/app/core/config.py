import os
from pydantic import BaseModel


class Settings(BaseModel):
    APP_NAME: str = "FocusFlow HLR Study Planner"
    VERSION: str = "2.0.0"
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./focusflow.db")
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    RETENTION_THRESHOLD: float = 0.7  # Default probability threshold for review
    DEFAULT_DAILY_MINUTES: int = 60


settings = Settings()
