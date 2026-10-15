from datetime import datetime
from typing import Any, Literal
from pydantic import BaseModel, Field, ConfigDict


# --- Concept & Question Schemas ---
class QuestionCreate(BaseModel):
    text: str = Field(min_length=3)
    options: list[str] = Field(min_length=2)
    answer_index: int = Field(ge=0)
    explanation: str | None = None
    status: Literal["draft", "approved", "flagged"] = "approved"


class QuestionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    concept_id: int
    text: str
    options: list[str]
    answer_index: int
    explanation: str | None
    status: str
    created_at: datetime


class ConceptCreate(BaseModel):
    subject_id: int
    topic_id: int | None = None
    name: str = Field(min_length=1, max_length=120)
    description: str | None = None


class ConceptResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    subject_id: int
    topic_id: int | None
    name: str
    description: str | None
    created_at: datetime
    # Current HLR state metrics
    h_hat: float | None = None
    p_hat_current: float | None = None
    total_correct: int | None = 0
    total_incorrect: int | None = 0
    next_review_at: datetime | None = None


# --- Material Upload & Generation ---
class MaterialUploadRequest(BaseModel):
    subject_id: int
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=10)


class MaterialUploadResponse(BaseModel):
    material_id: int
    subject_id: int
    title: str
    concepts_generated: int
    questions_generated: int
    concepts: list[ConceptResponse]


# --- Quiz & Session Schemas ---
class StartQuizRequest(BaseModel):
    user_id: int = 1
    subject_id: int | None = None
    concept_ids: list[int] | None = None
    limit: int = 10


class QuizQuestionItem(BaseModel):
    question_id: int
    concept_id: int
    concept_name: str
    text: str
    options: list[str]


class StartQuizResponse(BaseModel):
    session_id: int
    user_id: int
    subject_id: int | None
    questions: list[QuizQuestionItem]


class AnswerSubmitRequest(BaseModel):
    event_id: str = Field(description="Unique event ID for idempotent answer logging")
    question_id: int
    selected_index: int


class AnswerSubmitResponse(BaseModel):
    event_id: str
    is_correct: bool
    correct_index: int
    explanation: str | None
    already_recorded: bool = False


class CompleteSessionResponse(BaseModel):
    session_id: int
    total_attempts: int
    total_correct: int
    session_accuracy: float
    concepts_updated: list[dict[str, Any]]
    completed_at: datetime


# --- Dashboard & Plan Schemas ---
class SubjectSummary(BaseModel):
    subject_id: int
    name: str
    color: str
    total_concepts: int
    avg_p_hat: float
    due_concepts_count: int
    weak_concepts_count: int  # p_hat < 0.6


class DashboardResponse(BaseModel):
    user_id: int
    overall_retention: float
    total_due_concepts: int
    subjects: list[SubjectSummary]
    due_concepts: list[ConceptResponse]


class PlanConceptItem(BaseModel):
    concept_id: int
    concept_name: str
    subject_name: str
    subject_color: str
    h_hat: float
    current_p: float
    due_status: Literal["critical", "due", "learning", "fresh"]
    allocated_minutes: int


class DailyPlan(BaseModel):
    date_str: str
    day_name: str
    total_minutes: int
    concepts: list[PlanConceptItem]


class PlanResponse(BaseModel):
    generated_at: datetime
    daily_budget_minutes: int
    plan: list[DailyPlan]


# --- Curve Visualization ---
class CurvePoint(BaseModel):
    day: float
    probability: float
    threshold: float


class HistoryPoint(BaseModel):
    session_id: int
    recorded_at: datetime
    delta_days: float
    observed_p: float


class ConceptCurveResponse(BaseModel):
    concept_id: int
    concept_name: str
    subject_name: str
    h_hat: float
    current_delta_days: float
    current_p: float
    threshold: float
    next_review_days: float
    curve_points: list[CurvePoint]
    practice_history: list[HistoryPoint]


# --- Settings ---
class SettingsUpdateRequest(BaseModel):
    daily_minutes: int = Field(ge=10, le=480)
    subject_priorities: dict[str, float] = Field(default_factory=dict)
    exam_dates: dict[str, str] = Field(default_factory=dict)


class SettingsResponse(BaseModel):
    user_id: int
    daily_minutes: int
    subject_priorities: dict[str, float]
    exam_dates: dict[str, str]
