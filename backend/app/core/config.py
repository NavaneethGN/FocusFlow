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

    def get_gemini_api_key(self) -> str:
        # Dynamically re-check .env in case user saved it after startup
        try:
            from dotenv import load_dotenv
            cur = Path(__file__).resolve()
            backend_env = cur.parent.parent.parent / ".env"
            root_env = cur.parent.parent.parent.parent / ".env"
            if backend_env.exists():
                load_dotenv(dotenv_path=backend_env, override=True)
            if root_env.exists():
                load_dotenv(dotenv_path=root_env, override=True)
        except Exception:
            pass
        return os.getenv("GEMINI_API_KEY", "").strip() or self.GEMINI_API_KEY.strip()


settings = Settings()
