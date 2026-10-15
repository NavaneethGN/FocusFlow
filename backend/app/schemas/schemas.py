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
    half_life_days: float | None = None
    p_hat: float | None = None
    delta_days: float | None = 0.0
    is_due: bool | None = False
    subject: str | None = None
    topic: str | None = None
    total_correct: int | None = 0
    total_incorrect: int | None = 0
    next_review_at: datetime | None = None


# --- Material Upload & Generation ---
class MaterialUploadRequest(BaseModel):
    subject_id: int | None = 1
    subject: str | None = "General"
    topic: str | None = "General"
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=10)


class MaterialUploadResponse(BaseModel):
    material_id: int
    subject_id: int
    title: str
    concepts_generated: int
    questions_generated: int
    concepts: list[ConceptResponse]
    concept: Any | None = None
    generated_questions: list[Any] | None = None


# --- Quiz & Session Schemas ---
class StartQuizRequest(BaseModel):
    user_id: int = 1
    subject_id: int | None = None
    subject: str | None = None
    concept_id: str | None = None
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
    overall_retention_score: float | None = None
    total_concepts: int | None = None
    due_concepts_count: int | None = None
    weak_concepts_count: int | None = None
    daily_study_goal_minutes: int | None = 45
    minutes_studied_today: int | None = 32
    streak_days: int | None = 8
    retention_threshold: float | None = 0.70
    weakest_concepts: list[Any] | None = None


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
    date: str | None = None
    daily_minutes_goal: int | None = None
    total_scheduled_minutes: int | None = None
    due_concepts_total: int | None = None
    blocks: list[Any] | None = None


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


# --- AI Features (Chatbot, Doubt Solver, Mnemonic Lab) ---
class ChatMessage(BaseModel):
    role: Literal["user", "model", "assistant"]
    content: str


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)
    history: list[ChatMessage] = Field(default_factory=list)
    subject: str | None = None
    persona: Literal["socratic", "exam_prep", "eli5"] = "socratic"
    concept_context: str | None = None


class ChatResponse(BaseModel):
    reply: str
    persona: str
    ai_powered: bool
    model: str
    suggested_followups: list[str] = Field(default_factory=list)


class DoubtSolveRequest(BaseModel):
    doubt: str = Field(min_length=3)
    subject: str = "General"
    concept_context: str | None = None
    difficulty: Literal["Easy", "Medium", "Hard"] = "Medium"


class DoubtSolveResponse(BaseModel):
    doubt: str
    subject: str
    core_intuition: str
    step_by_step_solution: list[str]
    common_pitfalls: list[str]
    retention_hook: str
    verification_challenge: dict[str, Any]
    ai_powered: bool
    model: str


class MnemonicRequest(BaseModel):
    concept_name: str = Field(min_length=2)
    topic: str | None = ""
    subject: str | None = "General"


class FlashcardItem(BaseModel):
    front: str
    back: str
    hint: str | None = None


class MnemonicResponse(BaseModel):
    concept_name: str
    subject: str
    story_mnemonic: str
    acronym_or_rhyme: str
    real_world_metaphor: str
    key_takeaway: str
    flashcards: list[FlashcardItem]
    ai_powered: bool
    model: str

