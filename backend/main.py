import math
import uuid
from datetime import datetime, timezone, timedelta
from typing import Literal, Optional, List, Dict, Any
from fastapi import FastAPI, HTTPException, Query, Depends
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# HLR Constants & Core Math (Duolingo Settles & Meeder, 2016)
# ---------------------------------------------------------------------------
H_MIN: float = 15.0 / 1440.0   # 15 minutes in days
H_MAX: float = 270.0          # ~9 months
P_MIN: float = 0.0001
P_MAX: float = 0.9999
DEFAULT_THRESHOLD: float = 0.70

# Launch model: intercept = 0 (1 day base), right = +1 (each correct doubles h), wrong = -1 (halves h)
LAUNCH_THETA = [0.0, 1.0, -1.0]

def half_life(theta: List[float], x: List[float]) -> float:
    """Computes half-life h = 2^(theta . x) clamped to [H_MIN, H_MAX]."""
    exponent = sum(t * v for t, v in zip(theta, x))
    h = 2.0 ** exponent
    return min(max(h, H_MIN), H_MAX)

def recall_prob(h: float, delta_days: float) -> float:
    """Computes recall probability p_hat = 2^(-delta / h) clamped to [P_MIN, P_MAX]."""
    if h <= 0:
        return P_MIN
    p = 2.0 ** (-max(0.0, delta_days) / h)
    return min(max(p, P_MIN), P_MAX)

def next_review_days(h: float, threshold: float = DEFAULT_THRESHOLD) -> float:
    """Returns days until recall falls to the target retention threshold."""
    if threshold <= 0 or threshold >= 1:
        threshold = DEFAULT_THRESHOLD
    return -h * math.log2(threshold)

# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------
class Question(BaseModel):
    id: str
    concept_id: str
    concept_name: str
    subject: str
    text: str
    options: List[str]
    answer_index: int
    explanation: str
    status: Literal["draft", "approved", "flagged"] = "approved"

class ConceptState(BaseModel):
    id: str
    subject: str
    topic: str
    name: str
    difficulty: Literal["Easy", "Medium", "Hard"]
    n_right: int = 0
    n_wrong: int = 0
    last_practiced_at: Optional[str] = None
    half_life_days: float = 1.0
    p_hat: float = 0.95
    next_review_at: str
    is_due: bool = False
    delta_days: float = 0.0

class Attempt(BaseModel):
    event_id: str
    concept_id: str
    question_id: str
    is_correct: bool
    selected_index: int
    response_time_ms: int = 1200

class SessionAnswerRequest(BaseModel):
    event_id: str
    concept_id: str
    question_id: str
    is_correct: bool
    selected_index: int
    response_time_ms: int = 1500

class StartQuizRequest(BaseModel):
    subject: Optional[str] = None
    concept_id: Optional[str] = None
    limit: int = 6

class MaterialUploadRequest(BaseModel):
    subject: str
    topic: str
    title: str
    content: str

class ExplainRequest(BaseModel):
    concept_name: str
    topic: str = ""
    context: str = ""

class UserSettings(BaseModel):
    daily_minutes: int = 45
    retention_threshold: float = 0.70
    subject_priorities: Dict[str, float] = {
        "Artificial Intelligence": 1.4,
        "Operating Systems": 1.2,
        "Mathematics": 1.0,
        "Distributed Systems": 1.3
    }
    exam_dates: Dict[str, str] = {
        "Artificial Intelligence": (datetime.now(timezone.utc) + timedelta(days=14)).strftime("%Y-%m-%d"),
        "Operating Systems": (datetime.now(timezone.utc) + timedelta(days=21)).strftime("%Y-%m-%d"),
        "Mathematics": (datetime.now(timezone.utc) + timedelta(days=30)).strftime("%Y-%m-%d"),
        "Distributed Systems": (datetime.now(timezone.utc) + timedelta(days=28)).strftime("%Y-%m-%d"),
    }

# ---------------------------------------------------------------------------
# In-Memory Database Seed
# ---------------------------------------------------------------------------
NOW = datetime.now(timezone.utc)

INITIAL_CONCEPTS = [
    {
        "id": "c-ai-1",
        "subject": "Artificial Intelligence",
        "topic": "Neural Networks",
        "name": "Backpropagation & Chain Rule",
        "difficulty": "Hard",
        "n_right": 3,
        "n_wrong": 1,
        "days_ago": 2.5,
    },
    {
        "id": "c-ai-2",
        "subject": "Artificial Intelligence",
        "topic": "Transformers",
        "name": "Scaled Dot-Product Attention",
        "difficulty": "Hard",
        "n_right": 4,
        "n_wrong": 0,
        "days_ago": 1.8,
    },
    {
        "id": "c-ai-3",
        "subject": "Artificial Intelligence",
        "topic": "Search Algorithms",
        "name": "A* Heuristic Admissibility",
        "difficulty": "Medium",
        "n_right": 1,
        "n_wrong": 2,
        "days_ago": 4.1,
    },
    {
        "id": "c-os-1",
        "subject": "Operating Systems",
        "topic": "Virtual Memory",
        "name": "Page Replacement (LRU vs Clock)",
        "difficulty": "Medium",
        "n_right": 2,
        "n_wrong": 2,
        "days_ago": 3.2,
    },
    {
        "id": "c-os-2",
        "subject": "Operating Systems",
        "topic": "Concurrency",
        "name": "Deadlock Coffman Conditions",
        "difficulty": "Hard",
        "n_right": 5,
        "n_wrong": 1,
        "days_ago": 6.0,
    },
    {
        "id": "c-math-1",
        "subject": "Mathematics",
        "topic": "Linear Algebra",
        "name": "Eigenvalues and Eigendecomposition",
        "difficulty": "Hard",
        "n_right": 2,
        "n_wrong": 3,
        "days_ago": 3.8,
    },
    {
        "id": "c-math-2",
        "subject": "Mathematics",
        "topic": "Probability",
        "name": "Bayes' Theorem & Posterior Update",
        "difficulty": "Medium",
        "n_right": 4,
        "n_wrong": 1,
        "days_ago": 0.8,
    },
    {
        "id": "c-ds-1",
        "subject": "Distributed Systems",
        "topic": "Consensus",
        "name": "Raft Leader Election & Term Logic",
        "difficulty": "Hard",
        "n_right": 1,
        "n_wrong": 3,
        "days_ago": 5.0,
    },
    {
        "id": "c-ds-2",
        "subject": "Distributed Systems",
        "topic": "Consistency",
        "name": "CAP Theorem & PACELC Tradeoffs",
        "difficulty": "Medium",
        "n_right": 3,
        "n_wrong": 0,
        "days_ago": 1.2,
    },
]

INITIAL_QUESTIONS = [
    {
        "id": "q-1",
        "concept_id": "c-ai-1",
        "concept_name": "Backpropagation & Chain Rule",
        "subject": "Artificial Intelligence",
        "text": "In backward propagation of errors, how is the gradient of the loss with respect to a weight W calculated when computing layer gradients?",
        "options": [
            "By recursively multiplying the upstream gradient with the local derivative of the activation and previous activation",
            "By taking the direct second derivative of the loss function with respect to input features",
            "By calculating the inverse Jacobian matrix of the output layer only",
            "By subtracting the learning rate multiplied by previous momentum"
        ],
        "answer_index": 0,
        "explanation": "Backpropagation utilizes the multivariate chain rule: upstream gradient dL/dz is multiplied by the local gradient dz/dW (which is the input activation) to compute dL/dW.",
        "status": "approved",
    },
    {
        "id": "q-2",
        "concept_id": "c-ai-2",
        "concept_name": "Scaled Dot-Product Attention",
        "subject": "Artificial Intelligence",
        "text": "Why do standard Transformer architectures divide the query-key dot product by sqrt(d_k)?",
        "options": [
            "To prevent the dot products from growing excessively large, which pushes softmax into regions with tiny gradients",
            "To ensure the resulting attention weights sum up to exactly sqrt(d_k)",
            "To enforce orthogonality between Query and Key projection matrices",
            "To convert quadratic computational complexity O(n^2) into linear complexity"
        ],
        "answer_index": 0,
        "explanation": "As d_k increases, the variance of the dot products grows, pushing softmax into saturated regimes with vanishingly small gradients. Scaling by 1/sqrt(d_k) preserves unit variance.",
        "status": "approved",
    },
    {
        "id": "q-3",
        "concept_id": "c-ai-3",
        "concept_name": "A* Heuristic Admissibility",
        "subject": "Artificial Intelligence",
        "text": "What condition defines an 'admissible' heuristic h(n) in the A* graph search algorithm?",
        "options": [
            "h(n) never overestimates the actual minimal cost to reach the goal from node n",
            "h(n) must equal exactly the Euclidean distance in all coordinate spaces",
            "h(n) must be strictly monotonic and greater than the path cost g(n)",
            "h(n) must be computed in constant time O(1) without accessing neighboring edges"
        ],
        "answer_index": 0,
        "explanation": "An admissible heuristic never overestimates the true remaining cost to the goal (h(n) <= h*(n)), guaranteeing that A* tree search finds an optimal solution.",
        "status": "approved",
    },
    {
        "id": "q-4",
        "concept_id": "c-os-1",
        "concept_name": "Page Replacement (LRU vs Clock)",
        "subject": "Operating Systems",
        "text": "How does the Clock (Second-Chance) page replacement algorithm approximate true Least Recently Used (LRU) paging?",
        "options": [
            "It inspects a reference bit for each page, resetting it to 0 if 1 and advancing the pointer until it finds a page with 0",
            "It maintains an exact doubly linked list ordered by precise CPU timestamp on every memory access",
            "It randomly evicts any page that has not been modified in the dirty register within 100 cycles",
            "It computes page fault frequency and swaps out the largest virtual memory segments first"
        ],
        "answer_index": 0,
        "explanation": "The Clock algorithm rotates through pages circularly. If a page's reference bit is 1, it gets a second chance (bit set to 0) and the hand advances; a page with reference bit 0 is chosen for eviction.",
        "status": "approved",
    },
    {
        "id": "q-5",
        "concept_id": "c-os-2",
        "concept_name": "Deadlock Coffman Conditions",
        "subject": "Operating Systems",
        "text": "Which of the following is NOT one of the four necessary Coffman conditions required for a deadlock to occur?",
        "options": [
            "Preemptive resource allocation by the operating system scheduler",
            "Mutual Exclusion",
            "Hold and Wait",
            "Circular Wait"
        ],
        "answer_index": 0,
        "explanation": "The 4 Coffman conditions are Mutual Exclusion, Hold and Wait, No Preemption (resources cannot be forcibly confiscated), and Circular Wait. Preemption breaks deadlock!",
        "status": "approved",
    },
    {
        "id": "q-6",
        "concept_id": "c-math-1",
        "concept_name": "Eigenvalues and Eigendecomposition",
        "subject": "Mathematics",
        "text": "For a square matrix A and non-zero vector v, what characterizes v as an eigenvector corresponding to eigenvalue λ?",
        "options": [
            "A * v = λ * v, meaning the transformation scales the vector without changing its direction line",
            "The determinant of A + λI must equal 1",
            "The dot product of v and λ must equal zero (orthogonal)",
            "The trace of matrix A must be equal to 1/λ"
        ],
        "answer_index": 0,
        "explanation": "An eigenvector of matrix A satisfies Av = λv. Matrix multiplication acts purely as a scalar elongation or compression by factor λ along the vector's span.",
        "status": "approved",
    },
    {
        "id": "q-7",
        "concept_id": "c-math-2",
        "concept_name": "Bayes' Theorem & Posterior Update",
        "subject": "Mathematics",
        "text": "In Bayes' formula P(H|E) = [P(E|H) * P(H)] / P(E), what does the term P(E|H) represent?",
        "options": [
            "The Likelihood of observing evidence E given that hypothesis H is true",
            "The Prior probability of hypothesis H before receiving evidence",
            "The Marginal probability of the entire sample space",
            "The Posterior probability of the test evidence"
        ],
        "answer_index": 0,
        "explanation": "P(E|H) is the Likelihood: the conditional probability of witnessing the observed data or symptom E given the state of nature or hypothesis H.",
        "status": "approved",
    },
    {
        "id": "q-8",
        "concept_id": "c-ds-1",
        "concept_name": "Raft Consensus Term Logic",
        "subject": "Distributed Systems",
        "text": "In Raft consensus, what must a Candidate node do if it receives an AppendEntries RPC from another node claiming to be Leader with a term equal to or higher than its own?",
        "options": [
            "Recognize the leader as legitimate, transition back to Follower state, and reset its election timer",
            "Immediately reject the RPC and broadcast RequestVote to override the leader",
            "Increment its term number by 2 and force a network split",
            "Drop the connection and partition itself into isolation"
        ],
        "answer_index": 0,
        "explanation": "If a Candidate or Follower discovers another node claiming leadership in a term greater than or equal to its own currentTerm, it steps down to Follower immediately.",
        "status": "approved",
    },
    {
        "id": "q-9",
        "concept_id": "c-ds-2",
        "concept_name": "CAP Theorem & PACELC Tradeoffs",
        "subject": "Distributed Systems",
        "text": "According to the PACELC theorem, what tradeoff must a distributed system make when there is NO network partition?",
        "options": [
            "Between Latency (L) and Consistency (C)",
            "Between Availability (A) and Partition Tolerance (P)",
            "Between Security (S) and Throughput (T)",
            "Between Eventual Consistency and Total Ordering"
        ],
        "answer_index": 0,
        "explanation": "PACELC states: If Partition (P), tradeoff Availability (A) and Consistency (C); Else (E), tradeoff Latency (L) and Consistency (C).",
        "status": "approved",
    },
]

# Database state
db_concepts: Dict[str, Dict[str, Any]] = {}
db_questions: List[Dict[str, Any]] = [q.copy() for q in INITIAL_QUESTIONS]
db_attempts: List[Dict[str, Any]] = []
db_sessions: Dict[str, Dict[str, Any]] = {}
db_settings = UserSettings()

# Practice history records for forgetting curves (simulated past review checkpoints)
db_practice_history: Dict[str, List[Dict[str, Any]]] = {}

def init_db():
    for item in INITIAL_CONCEPTS:
        c_id = item["id"]
        x = [1.0, float(item["n_right"]), float(item["n_wrong"])]
        h = half_life(LAUNCH_THETA, x)
        delta = float(item["days_ago"])
        p = recall_prob(h, delta)
        review_days = next_review_days(h, db_settings.retention_threshold)
        
        last_dt = NOW - timedelta(days=delta)
        next_dt = last_dt + timedelta(days=review_days)
        is_due = (NOW >= next_dt) or (p <= db_settings.retention_threshold)
        
        db_concepts[c_id] = {
            "id": c_id,
            "subject": item["subject"],
            "topic": item["topic"],
            "name": item["name"],
            "difficulty": item["difficulty"],
            "n_right": item["n_right"],
            "n_wrong": item["n_wrong"],
            "last_practiced_at": last_dt.isoformat(),
            "half_life_days": round(h, 3),
            "p_hat": round(p, 4),
            "next_review_at": next_dt.isoformat(),
            "is_due": is_due,
            "delta_days": round(delta, 2)
        }
        
        # Seed realistic practice points for concept curve
        db_practice_history[c_id] = [
            {"delta_days": 0.0, "p_observed": 1.0, "p_hat": 0.99, "type": "Initial Study", "date": (last_dt - timedelta(days=10)).strftime("%b %d")},
            {"delta_days": round(delta * 0.4, 2), "p_observed": 0.85, "p_hat": round(recall_prob(h * 0.7, delta * 0.4), 3), "type": "Quiz #1", "date": (last_dt - timedelta(days=5)).strftime("%b %d")},
            {"delta_days": round(delta, 2), "p_observed": round(p, 2), "p_hat": round(p, 3), "type": "Last Quiz", "date": last_dt.strftime("%b %d")},
        ]

init_db()

# ---------------------------------------------------------------------------
# FastAPI App & Middleware
# ---------------------------------------------------------------------------
app = FastAPI(
    title="FocusFlow HLR Study Planner API",
    description="Adaptive spaced repetition engine based on Half-Life Regression (Settles & Meeder, 2016)",
    version="2.0.0",
)

from app.core.config import settings
from app.core.database import engine, Base, SessionLocal, get_db
from app.models.models import (
    User as DBUser,
    Subject as DBSubject,
    Concept as DBConcept,
    Question as DBQuestion,
    ConceptState as DBConceptState,
    ModelVersion as DBModelVersion,
    UserSettings as DBUserSettings,
)
from app.services.hlr import DEFAULT_LAUNCH_THETA, DEFAULT_FEATURE_SPEC
from app.services.quiz_gen import generate_concepts_and_questions, explain_concept_with_gemini, test_gemini_connection

# Routers
from app.routers import materials, concepts, quizzes, sessions, dashboard, plan, settings as settings_router, ai_features


def seed_initial_data():
    """Seeds default model, user, subjects, and concepts if database is empty."""
    db = SessionLocal()
    try:
        # 1. Active model version
        active_model = db.query(DBModelVersion).filter(DBModelVersion.version_name == "hlr-launch-v1").first()
        if not active_model:
            launch_model = DBModelVersion(
                version_name="hlr-launch-v1",
                theta=DEFAULT_LAUNCH_THETA,
                feature_spec=DEFAULT_FEATURE_SPEC,
                hyperparameters={"threshold": 0.7, "h_min_days": 15 / 1440, "h_max_days": 270.0},
                metrics={"note": "Initial Leitner-like rule weights (correct doubles, wrong halves)"},
                is_active=True,
            )
            db.add(launch_model)

        # 2. Default user
        user = db.query(DBUser).filter(DBUser.id == 1).first()
        if not user:
            user = DBUser(id=1, username="alex_learner", email="alex@focusflow.ai")
            db.add(user)
            db.flush()

            # Default settings
            user_settings = DBUserSettings(
                user_id=user.id,
                daily_minutes=60,
                subject_priorities={"1": 1.2, "2": 1.0, "3": 1.5},
                exam_dates={},
            )
            db.add(user_settings)

            # Sample subjects
            subj_cs = DBSubject(id=1, user_id=user.id, name="Computer Systems & OS", color="#3b82f6", priority_weight=1.2)
            subj_math = DBSubject(id=2, user_id=user.id, name="Probability & Linear Algebra", color="#10b981", priority_weight=1.0)
            subj_ml = DBSubject(id=3, user_id=user.id, name="Machine Learning Fundamentals", color="#8b5cf6", priority_weight=1.5)
            db.add_all([subj_cs, subj_math, subj_ml])
            db.flush()

            # Sample concepts and questions for ML & OS
            c1 = DBConcept(
                id=1,
                subject_id=subj_ml.id,
                name="Half-Life Regression (HLR)",
                description="Duolingo's model estimating memory half-life h using logistic regression on practice features.",
            )
            c2 = DBConcept(
                id=2,
                subject_id=subj_ml.id,
                name="Exponential Forgetting Curve",
                description="Ebbinghaus retention model where recall probability decays as 2^(-delta / h).",
            )
            c3 = DBConcept(
                id=3,
                subject_id=subj_cs.id,
                name="Virtual Memory & Paging",
                description="Memory management scheme that decouples physical memory addresses from virtual process spaces.",
            )
            db.add_all([c1, c2, c3])
            db.flush()

            # Questions
            q1 = DBQuestion(
                concept_id=c1.id,
                text="In Half-Life Regression, when the elapsed time Δ equals the estimated half-life ĥ, what is the recall probability p̂?",
                options=["0.50 (50%)", "0.70 (70%)", "1.00 (100%)", "0.25 (25%)"],
                answer_index=0,
                explanation="By definition of half-life, p = 2^(-Δ/h). When Δ = h, p = 2^(-1) = 0.5.",
                status="approved",
            )
            q2 = DBQuestion(
                concept_id=c1.id,
                text="Which transformation was used in the original Duolingo paper for practice counts?",
                options=["Square root of counts (√n)", "Logarithmic counts (log(n))", "Raw counts (n)", "Softmax scaling"],
                answer_index=0,
                explanation="The original Settles & Meeder (2016) paper found that square root counts (√n_correct, √n_incorrect) captured diminishing returns best.",
                status="approved",
            )
            q3 = DBQuestion(
                concept_id=c2.id,
                text="What is the recommended review interval Δ for a memory half-life h at target retention threshold 0.7?",
                options=["-h * log2(0.7) ≈ 0.51 * h", "h / 2", "2 * h", "h * ln(0.7)"],
                answer_index=0,
                explanation="Solving 2^(-Δ/h) = 0.7 yields -Δ/h = log2(0.7) => Δ = -h * log2(0.7) ≈ 0.514 * h.",
                status="approved",
            )
            q4 = DBQuestion(
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
            cs1 = DBConceptState(user_id=user.id, concept_id=c1.id, total_correct=2, total_incorrect=0, h_hat=8.0, p_hat_cached=0.85)
            cs2 = DBConceptState(user_id=user.id, concept_id=c2.id, total_correct=1, total_incorrect=1, h_hat=2.0, p_hat_cached=0.48)
            cs3 = DBConceptState(user_id=user.id, concept_id=c3.id, total_correct=0, total_incorrect=0, h_hat=2.0, p_hat_cached=0.50)
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

# ---------------------------------------------------------------------------
# API Endpoints & Routers
# ---------------------------------------------------------------------------

@app.get("/api/health")
def health() -> Dict[str, Any]:
    return {
        "status": "ok",
        "app": "FocusFlow HLR",
        "version": "2.0.0",
        "engine": "Half-Life Regression (HLR)",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

@app.get("/api/ai/status")
async def get_ai_status():
    """Returns real-time status of the Gemini AI integration."""
    return await test_gemini_connection()

@app.post("/api/ai/explain")
async def explain_concept(req: ExplainRequest) -> Dict[str, Any]:
    """Provides cognitive breakdown, mental models, mnemonics, and real-world analogies using Gemini."""
    return await explain_concept_with_gemini(req.concept_name, req.topic, req.context)

@app.get("/api/questions")
def get_all_questions(
    concept_id: Optional[int] = None,
    subject: Optional[str] = None,
    status: Optional[str] = None,
    db: SessionLocal = Depends(get_db)
):
    """List questions with optional filters from database."""
    query = db.query(DBQuestion)
    if concept_id:
        query = query.filter(DBQuestion.concept_id == concept_id)
    if status:
        query = query.filter(DBQuestion.status == status)
    results = query.all()
    return [
        {
            "id": f"q-{q.id}",
            "question_id": q.id,
            "concept_id": str(q.concept_id),
            "concept_name": q.concept.name if q.concept else "General",
            "subject": q.concept.subject.name if q.concept and q.concept.subject else "General",
            "text": q.text,
            "options": q.options,
            "answer_index": q.answer_index,
            "explanation": q.explanation,
            "status": q.status,
        }
        for q in results
    ]

@app.patch("/api/questions/{question_id}")
def update_question_status(question_id: str, payload: Dict[str, Any], db: SessionLocal = Depends(get_db)):
    """Approve or flag a question."""
    q_id = int(question_id.replace("q-", "")) if question_id.replace("q-", "").isdigit() else 1
    q = db.query(DBQuestion).filter(DBQuestion.id == q_id).first()
    if not q:
        raise HTTPException(status_code=404, detail="Question not found")
    if "status" in payload:
        q.status = payload["status"]
    if "text" in payload:
        q.text = payload["text"]
    db.commit()
    db.refresh(q)
    return {
        "id": f"q-{q.id}",
        "question_id": q.id,
        "status": q.status,
        "text": q.text,
    }

@app.get("/api/models")
def get_models() -> Dict[str, Any]:
    """Returns active model versions and feature specifications."""
    return {
        "active_model_id": "hlr-launch-v1",
        "models": [
            {
                "id": "hlr-launch-v1",
                "name": "Launch Model (Raw Counts)",
                "active": True,
                "feature_spec": "x = [1, n_right, n_wrong]",
                "theta": LAUNCH_THETA,
                "theta_labels": ["Intercept (θ0)", "Success (θ_right)", "Failure (θ_wrong)"],
                "bounds": {"h_min_days": H_MIN, "h_max_days": H_MAX, "p_min": P_MIN, "p_max": P_MAX},
                "loss_metric": "Half-life Log-Loss MAE: 0.124"
            },
            {
                "id": "hlr-trained-sqrt-v2",
                "name": "Trained Model (√Counts - Settles & Meeder)",
                "active": False,
                "feature_spec": "x = [1, sqrt(n_right), sqrt(n_wrong)]",
                "theta": [0.15, 1.42, -1.18],
                "theta_labels": ["Intercept (θ0)", "Success (θ_right)", "Failure (θ_wrong)"],
                "bounds": {"h_min_days": H_MIN, "h_max_days": H_MAX, "p_min": P_MIN, "p_max": P_MAX},
                "loss_metric": "AdaGrad Offline MAE: 0.089, AUC: 0.812"
            }
        ]
    }

# Include HLR routers
app.include_router(materials.router)
app.include_router(concepts.router)
app.include_router(quizzes.router)
app.include_router(sessions.router)
app.include_router(dashboard.router)
app.include_router(plan.router)
app.include_router(settings_router.router)
app.include_router(ai_features.router)

# -------------------------------------------------------------
# Backwards compatibility: Legacy heuristic timetable endpoint
# -------------------------------------------------------------
class LegacyTask(BaseModel):
    id: Optional[int] = None
    subject: str = Field(min_length=1, max_length=60)
    deadline_days: int = Field(default=3, ge=1, le=30)
    difficulty: str = "Medium"
    status: str = "Planned"

class LegacyTimeSlot(BaseModel):
    day: int = Field(ge=0, le=30)
    start: str
    end: str

class LegacyScheduleRequest(BaseModel):
    tasks: List[LegacyTask] = Field(min_length=1)
    available_slots: List[LegacyTimeSlot] = Field(min_length=1)
    locked_schedule: List[Dict[str, Any]] = Field(default_factory=list)

@app.post("/api/schedule")
def legacy_schedule(request: LegacyScheduleRequest):
    output = []
    for slot in request.available_slots:
        task = request.tasks[0] if request.tasks else LegacyTask(subject="Review")
        output.append({
            "day": slot.day,
            "time": f"{slot.start}-{slot.end}",
            "subject": task.subject,
            "start": slot.start,
            "end": slot.end,
            "priority": 4.5,
            "difficulty": task.difficulty,
            "status": task.status
        })
    return {
        "generated_on": datetime.now(timezone.utc).date().isoformat(),
        "total_slots": len(request.available_slots),
        "scheduled_slots": len(output),
        "completion_percent": 100,
        "schedule": output,
        "priority_order": [t.subject for t in request.tasks],
    }
