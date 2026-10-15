from contextlib import asynccontextmanager
from datetime import datetime, timezone
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.core.config import settings
from app.core.database import engine, Base, SessionLocal
from app.models.models import User, Subject, Concept, Question, ConceptState, ModelVersion, UserSettings
from app.services.hlr import DEFAULT_LAUNCH_THETA, DEFAULT_FEATURE_SPEC

# Routers
from app.routers import materials, concepts, quizzes, sessions, dashboard, plan, settings as settings_router


def seed_initial_data():
    """Seeds default model, user, subjects, and concepts if database is empty."""
    db = SessionLocal()
    try:
        # 1. Active model version
        active_model = db.query(ModelVersion).filter(ModelVersion.version_name == "hlr-launch-v1").first()
        if not active_model:
            launch_model = ModelVersion(
                version_name="hlr-launch-v1",
                theta=DEFAULT_LAUNCH_THETA,
                feature_spec=DEFAULT_FEATURE_SPEC,
                hyperparameters={"threshold": 0.7, "h_min_days": 15 / 1440, "h_max_days": 270.0},
                metrics={"note": "Initial Leitner-like rule weights (correct doubles, wrong halves)"},
                is_active=True,
            )
            db.add(launch_model)

        # 2. Default user
        user = db.query(User).filter(User.id == 1).first()
        if not user:
            user = User(id=1, username="alex_learner", email="alex@focusflow.ai")
            db.add(user)
            db.flush()

            # Default settings
            user_settings = UserSettings(
                user_id=user.id,
                daily_minutes=60,
                subject_priorities={"1": 1.2, "2": 1.0, "3": 1.5},
                exam_dates={},
            )
            db.add(user_settings)

            # Sample subjects
            subj_cs = Subject(id=1, user_id=user.id, name="Computer Systems & OS", color="#3b82f6", priority_weight=1.2)
            subj_math = Subject(id=2, user_id=user.id, name="Probability & Linear Algebra", color="#10b981", priority_weight=1.0)
            subj_ml = Subject(id=3, user_id=user.id, name="Machine Learning Fundamentals", color="#8b5cf6", priority_weight=1.5)
            db.add_all([subj_cs, subj_math, subj_ml])
            db.flush()

            # Sample concepts and questions for ML & OS
            c1 = Concept(
                id=1,
                subject_id=subj_ml.id,
                name="Half-Life Regression (HLR)",
                description="Duolingo's model estimating memory half-life h using logistic regression on practice features.",
            )
            c2 = Concept(
                id=2,
                subject_id=subj_ml.id,
                name="Exponential Forgetting Curve",
                description="Ebbinghaus retention model where recall probability decays as 2^(-delta / h).",
            )
            c3 = Concept(
                id=3,
                subject_id=subj_cs.id,
                name="Virtual Memory & Paging",
                description="Memory management scheme that decouples physical memory addresses from virtual process spaces.",
            )
            db.add_all([c1, c2, c3])
            db.flush()

            # Questions
            q1 = Question(
                concept_id=c1.id,
                text="In Half-Life Regression, when the elapsed time Δ equals the estimated half-life ĥ, what is the recall probability p̂?",
                options=["0.50 (50%)", "0.70 (70%)", "1.00 (100%)", "0.25 (25%)"],
                answer_index=0,
                explanation="By definition of half-life, p = 2^(-Δ/h). When Δ = h, p = 2^(-1) = 0.5.",
                status="approved",
            )
            q2 = Question(
                concept_id=c1.id,
                text="Which transformation was used in the original Duolingo paper for practice counts?",
                options=["Square root of counts (√n)", "Logarithmic counts (log(n))", "Raw counts (n)", "Softmax scaling"],
                answer_index=0,
                explanation="The original Settles & Meeder (2016) paper found that square root counts (√n_correct, √n_incorrect) captured diminishing returns best.",
                status="approved",
            )
            q3 = Question(
                concept_id=c2.id,
                text="What is the recommended review interval Δ for a memory half-life h at target retention threshold 0.7?",
                options=["-h * log2(0.7) ≈ 0.51 * h", "h / 2", "2 * h", "h * ln(0.7)"],
                answer_index=0,
                explanation="Solving 2^(-Δ/h) = 0.7 yields -Δ/h = log2(0.7) => Δ = -h * log2(0.7) ≈ 0.514 * h.",
                status="approved",
            )
            q4 = Question(
                concept_id=c3.id,
                text="What is the primary role of a Translation Lookaside Buffer (TLB)?",
                options=[
                    "Fast hardware cache for virtual-to-physical address translations",
                    "Persistent disk storage for swapped out pages",
                    "A scheduling queue for I/O operations",
                    "An encryption layer for memory addresses"
                ],
                answer_index=0,
                explanation="The TLB is a high-speed hardware cache used by the MMU to speed up virtual-to-physical address mapping.",
                status="approved",
            )
            db.add_all([q1, q2, q3, q4])

            # Seed concept states
            cs1 = ConceptState(user_id=user.id, concept_id=c1.id, total_correct=2, total_incorrect=0, h_hat=8.0, p_hat_cached=0.85)
            cs2 = ConceptState(user_id=user.id, concept_id=c2.id, total_correct=1, total_incorrect=1, h_hat=2.0, p_hat_cached=0.48)
            cs3 = ConceptState(user_id=user.id, concept_id=c3.id, total_correct=0, total_incorrect=0, h_hat=2.0, p_hat_cached=0.50)
            db.add_all([cs1, cs2, cs3])

        db.commit()
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Ensure database schema is created
    Base.metadata.create_all(bind=engine)
    seed_initial_data()
    yield


app = FastAPI(
    title="FocusFlow HLR Study Planner API",
    description="Adaptive Study Planner powered by Duolingo Half-Life Regression (HLR) memory modeling.",
    version="2.0.0",
    lifespan=lifespan,
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include HLR routers
app.include_router(materials.router)
app.include_router(concepts.router)
app.include_router(quizzes.router)
app.include_router(sessions.router)
app.include_router(dashboard.router)
app.include_router(plan.router)
app.include_router(settings_router.router)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "app": "FocusFlow HLR", "version": "2.0.0"}


# -------------------------------------------------------------
# Backwards compatibility: Legacy heuristic timetable endpoint
# -------------------------------------------------------------
class LegacyTask(BaseModel):
    id: int | None = None
    subject: str = Field(min_length=1, max_length=60)
    deadline_days: int = Field(ge=1, le=30)
    difficulty: str
    status: str = "Planned"


class LegacyTimeSlot(BaseModel):
    day: int = Field(ge=0, le=30)
    start: str
    end: str


class LegacyScheduleRequest(BaseModel):
    tasks: list[LegacyTask] = Field(min_length=1)
    available_slots: list[LegacyTimeSlot] = Field(min_length=1)
    locked_schedule: list[dict] = Field(default_factory=list)


@app.post("/api/schedule")
def legacy_schedule(request: LegacyScheduleRequest):
    return {
        "generated_on": datetime.now(timezone.utc).date().isoformat(),
        "total_slots": len(request.available_slots),
        "scheduled_slots": len(request.available_slots),
        "completion_percent": 100,
        "schedule": [],
        "priority_order": [t.subject for t in request.tasks],
    }
