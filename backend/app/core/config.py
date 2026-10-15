import os
from pathlib import Path
from pydantic import BaseModel

try:
    from dotenv import load_dotenv
    # Load .env from backend directory or project root
    backend_env = Path(__file__).resolve().parent.parent.parent / ".env"
    load_dotenv(dotenv_path=backend_env)
    load_dotenv()
except ImportError:
    pass


class Settings(BaseModel):
    APP_NAME: str = "FocusFlow HLR Study Planner"
    VERSION: str = "2.0.0"
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./focusflow.db")
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    RETENTION_THRESHOLD: float = 0.7  # Default probability threshold for review
    DEFAULT_DAILY_MINUTES: int = 60


settings = Settings()
