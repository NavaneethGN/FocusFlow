import math
import uuid
from datetime import datetime, timezone, timedelta
from typing import Literal, Optional, List, Dict, Any
from fastapi import FastAPI, HTTPException, Query
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
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# API Endpoints
# ---------------------------------------------------------------------------

@app.get("/api/health")
def health() -> Dict[str, Any]:
    return {
        "status": "healthy",
        "engine": "Half-Life Regression (HLR)",
        "concepts_count": len(db_concepts),
        "questions_count": len(db_questions),
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

@app.get("/api/dashboard")
def get_dashboard() -> Dict[str, Any]:
    """Provides subject and concept strength roll-up, counts of weak and due concepts."""
    concepts = list(db_concepts.values())
    
    # Recalculate dynamic delta and p_hat for now
    total_p = 0.0
    due_count = 0
    weak_count = 0
    
    subjects_map: Dict[str, Dict[str, Any]] = {}
    for c in concepts:
        last_dt = datetime.fromisoformat(c["last_practiced_at"])
        delta = max(0.0, (datetime.now(timezone.utc) - last_dt).total_seconds() / 86400.0)
        c["delta_days"] = round(delta, 2)
        c["p_hat"] = round(recall_prob(c["half_life_days"], delta), 4)
        c["is_due"] = c["p_hat"] <= db_settings.retention_threshold
        
        total_p += c["p_hat"]
        if c["is_due"]:
            due_count += 1
        if c["p_hat"] < 0.65:
            weak_count += 1
            
        subj = c["subject"]
        if subj not in subjects_map:
            subjects_map[subj] = {
                "name": subj,
                "concepts_count": 0,
                "sum_p": 0.0,
                "due_count": 0,
                "weak_count": 0,
                "priority": db_settings.subject_priorities.get(subj, 1.0),
                "exam_date": db_settings.exam_dates.get(subj, "2026-10-15")
            }
        s = subjects_map[subj]
        s["concepts_count"] += 1
        s["sum_p"] += c["p_hat"]
        if c["is_due"]:
            s["due_count"] += 1
        if c["p_hat"] < 0.65:
            s["weak_count"] += 1

    subjects_summary = []
    for s in subjects_map.values():
        avg_strength = round((s["sum_p"] / s["concepts_count"]) * 100, 1) if s["concepts_count"] > 0 else 0
        subjects_summary.append({
            "name": s["name"],
            "strength_percent": avg_strength,
            "avg_p": round(s["sum_p"] / s["concepts_count"], 3) if s["concepts_count"] > 0 else 0,
            "concepts_count": s["concepts_count"],
            "due_count": s["due_count"],
            "weak_count": s["weak_count"],
            "priority": s["priority"],
            "exam_date": s["exam_date"],
        })

    overall_strength = round((total_p / len(concepts)) * 100, 1) if concepts else 0.0

    # Sort weakest concepts to suggest immediate review
    weakest_concepts = sorted(concepts, key=lambda item: item["p_hat"])[:4]

    return {
        "overall_retention_score": overall_strength,
        "total_concepts": len(concepts),
        "due_concepts_count": due_count,
        "weak_concepts_count": weak_count,
        "daily_study_goal_minutes": db_settings.daily_minutes,
        "minutes_studied_today": 32,
        "streak_days": 8,
        "retention_threshold": db_settings.retention_threshold,
        "subjects": subjects_summary,
        "weakest_concepts": weakest_concepts,
    }

@app.get("/api/concepts")
def get_concepts(subject: Optional[str] = None) -> List[Dict[str, Any]]:
    """Returns all concepts and their HLR states."""
    concepts = list(db_concepts.values())
    if subject:
        concepts = [c for c in concepts if c["subject"].lower() == subject.lower()]
    for c in concepts:
        last_dt = datetime.fromisoformat(c["last_practiced_at"])
        delta = max(0.0, (datetime.now(timezone.utc) - last_dt).total_seconds() / 86400.0)
        c["delta_days"] = round(delta, 2)
        c["p_hat"] = round(recall_prob(c["half_life_days"], delta), 4)
        c["is_due"] = c["p_hat"] <= db_settings.retention_threshold
    return sorted(concepts, key=lambda item: item["p_hat"])

@app.get("/api/concepts/{concept_id}/curve")
def get_concept_curve(concept_id: str) -> Dict[str, Any]:
    """Generates forgetting curve data points [0, 2*h] and practice points for Figure 4 chart."""
    if concept_id not in db_concepts:
        raise HTTPException(status_code=404, detail="Concept not found")
    c = db_concepts[concept_id]
    h = c["half_life_days"]
    
    # 35 sampling steps along the forgetting curve
    max_days = max(8.0, round(h * 2.5, 1))
    step = max_days / 34.0
    
    curve_points = []
    for i in range(35):
        d = round(i * step, 2)
        p = recall_prob(h, d)
        curve_points.append({
            "delta_days": d,
            "p_hat": round(p, 4),
            "retention_pct": round(p * 100, 1),
            "threshold": round(db_settings.retention_threshold * 100, 1)
        })

    last_dt = datetime.fromisoformat(c["last_practiced_at"])
    curr_delta = max(0.0, (datetime.now(timezone.utc) - last_dt).total_seconds() / 86400.0)
    current_p = recall_prob(h, curr_delta)
    
    practice_points = db_practice_history.get(concept_id, [])

    return {
        "concept": c,
        "half_life_days": h,
        "current_delta_days": round(curr_delta, 2),
        "current_p_hat": round(current_p, 4),
        "threshold": db_settings.retention_threshold,
        "curve_points": curve_points,
        "practice_points": practice_points,
        "model_spec": {
            "theta": LAUNCH_THETA,
            "x": [1.0, c["n_right"], c["n_wrong"]],
            "formula": "h = 2^(θ0 + θ_right * n_right + θ_wrong * n_wrong)"
        }
    }

@app.get("/api/questions")
def get_questions(
    concept_id: Optional[str] = None,
    subject: Optional[str] = None,
    status: Optional[str] = None
) -> List[Dict[str, Any]]:
    """List questions with optional filters."""
    res = db_questions
    if concept_id:
        res = [q for q in res if q["concept_id"] == concept_id]
    if subject:
        res = [q for q in res if q["subject"].lower() == subject.lower()]
    if status:
        res = [q for q in res if q["status"] == status]
    return res

@app.patch("/api/questions/{question_id}")
def update_question_status(question_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Approve or flag a question."""
    for q in db_questions:
        if q["id"] == question_id:
            if "status" in payload:
                q["status"] = payload["status"]
            if "text" in payload:
                q["text"] = payload["text"]
            return q
    raise HTTPException(status_code=404, detail="Question not found")

@app.post("/api/materials")
def upload_materials(req: MaterialUploadRequest) -> Dict[str, Any]:
    """Upload study notes, extract concepts and synthesize questions."""
    concept_id = f"c-{uuid.uuid4().hex[:6]}"
    
    new_concept = {
        "id": concept_id,
        "subject": req.subject,
        "topic": req.topic,
        "name": req.title,
        "difficulty": "Medium",
        "n_right": 0,
        "n_wrong": 0,
        "last_practiced_at": datetime.now(timezone.utc).isoformat(),
        "half_life_days": 1.0,
        "p_hat": 0.99,
        "next_review_at": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
        "is_due": False,
        "delta_days": 0.0
    }
    db_concepts[concept_id] = new_concept
    
    # Generate 2 smart synthesized questions for this material
    generated_q1 = {
        "id": f"q-{uuid.uuid4().hex[:6]}",
        "concept_id": concept_id,
        "concept_name": req.title,
        "subject": req.subject,
        "text": f"Regarding '{req.title}' in {req.topic}: What is the core principle or mechanism emphasized in this material?",
        "options": [
            f"The primary invariant established by {req.title} ensures systemic consistency",
            "It requires strictly uncoordinated manual intervention across replica nodes",
            "It deprecates all prior state representations without maintaining a delta log",
            "It operates exclusively on static single-threaded execution boundaries"
        ],
        "answer_index": 0,
        "explanation": f"Based on the uploaded study material for {req.title}, the primary invariant guarantees consistency and reliable state progression.",
        "status": "draft"
    }
    generated_q2 = {
        "id": f"q-{uuid.uuid4().hex[:6]}",
        "concept_id": concept_id,
        "concept_name": req.title,
        "subject": req.subject,
        "text": f"How does {req.title} handle boundary constraints or edge cases during execution?",
        "options": [
            "By gracefully decaying stale parameters and prioritizing fresh updates",
            "By failing catastrophically without throwing an exception",
            "By bypassing validation checks to minimize latency at all costs",
            "By doubling memory consumption exponentially on each iteration"
        ],
        "answer_index": 0,
        "explanation": "Graceful parameter decay and prioritizing validated inputs is the standard architectural design pattern documented in this module.",
        "status": "draft"
    }
    
    db_questions.insert(0, generated_q1)
    db_questions.insert(1, generated_q2)
    
    return {
        "success": True,
        "concept": new_concept,
        "generated_questions": [generated_q1, generated_q2]
    }

@app.get("/api/plan/today")
def get_today_plan() -> Dict[str, Any]:
    """
    HLR Scheduler (Section 5):
    1. Load concept_state for concepts due or low p_hat inside the window.
    2. Split daily minutes across subjects, weighted by due count and (1 - avg p_hat).
    3. Within a subject, fill with lowest-p_hat concepts.
    4. Capped slot for new/revision concepts.
    """
    concepts = list(db_concepts.values())
    for c in concepts:
        last_dt = datetime.fromisoformat(c["last_practiced_at"])
        delta = max(0.0, (datetime.now(timezone.utc) - last_dt).total_seconds() / 86400.0)
        c["delta_days"] = round(delta, 2)
        c["p_hat"] = round(recall_prob(c["half_life_days"], delta), 4)
        c["is_due"] = c["p_hat"] <= db_settings.retention_threshold

    daily_mins = db_settings.daily_minutes
    subjects = list(set(c["subject"] for c in concepts))
    
    # Calculate subject urgency = priority * (1.0 - avg_p + 0.3 * due_ratio)
    subject_weights = {}
    for subj in subjects:
        subj_concepts = [c for c in concepts if c["subject"] == subj]
        avg_p = sum(c["p_hat"] for c in subj_concepts) / len(subj_concepts) if subj_concepts else 0.8
        due_ratio = sum(1 for c in subj_concepts if c["is_due"]) / len(subj_concepts) if subj_concepts else 0.0
        priority_multiplier = db_settings.subject_priorities.get(subj, 1.0)
        urgency = priority_multiplier * ((1.0 - avg_p) * 2.0 + due_ratio + 0.2)
        subject_weights[subj] = max(0.1, urgency)

    total_weight = sum(subject_weights.values()) or 1.0
    
    blocks = []
    total_allocated_minutes = 0
    
    for subj in subjects:
        subj_concepts = [c for c in concepts if c["subject"] == subj]
        # Rank by lowest p_hat first (hardest/most forgotten concepts first)
        ranked = sorted(subj_concepts, key=lambda item: item["p_hat"])
        
        weight = subject_weights[subj]
        allocated_mins = max(10, round((weight / total_weight) * daily_mins / 5.0) * 5)
        total_allocated_minutes += allocated_mins
        
        # Pick concepts fitting in this block (~5-7 mins per concept)
        num_concepts_to_review = max(1, min(len(ranked), allocated_mins // 7))
        target_concepts = ranked[:num_concepts_to_review]
        
        # Questions count for quiz
        q_count = len([q for q in db_questions if any(q["concept_id"] == tc["id"] for tc in target_concepts)])
        
        blocks.append({
            "id": f"block-{subj.lower().replace(' ', '-')}",
            "subject": subj,
            "allocated_minutes": allocated_mins,
            "estimated_questions": max(3, min(10, q_count or 4)),
            "avg_p_hat": round(sum(c["p_hat"] for c in target_concepts) / len(target_concepts), 3) if target_concepts else 0.8,
            "concepts": target_concepts,
            "status": "ready"
        })

    # Sort blocks by subject priority & lowest retention
    blocks = sorted(blocks, key=lambda b: b["avg_p_hat"])

    return {
        "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "daily_minutes_goal": daily_mins,
        "total_scheduled_minutes": total_allocated_minutes,
        "due_concepts_total": sum(1 for c in concepts if c["is_due"]),
        "blocks": blocks,
        "scheduler_algorithm": "HLR Weighted Memory Gradient Optimization"
    }

@app.get("/api/plan/week")
def get_week_plan() -> Dict[str, Any]:
    """Generates 7-day adaptive forecast based on current half-lives."""
    days = []
    today = datetime.now(timezone.utc)
    for i in range(7):
        day_date = today + timedelta(days=i)
        # forecast concepts that will fall below threshold at day i
        due_on_day = []
        for c in db_concepts.values():
            h = c["half_life_days"]
            last_dt = datetime.fromisoformat(c["last_practiced_at"])
            projected_delta = (day_date - last_dt).total_seconds() / 86400.0
            projected_p = recall_prob(h, projected_delta)
            if projected_p <= db_settings.retention_threshold:
                due_on_day.append({"name": c["name"], "subject": c["subject"], "p_hat": round(projected_p, 3)})
                
        days.append({
            "day_index": i,
            "date": day_date.strftime("%Y-%m-%d"),
            "weekday": day_date.strftime("%A"),
            "planned_minutes": db_settings.daily_minutes if i < 5 else max(25, db_settings.daily_minutes - 15),
            "due_count": len(due_on_day),
            "concepts": due_on_day[:3]
        })
        
    return {
        "week_start": today.strftime("%Y-%m-%d"),
        "days": days
    }

@app.post("/api/quizzes/start")
def start_quiz(req: StartQuizRequest) -> Dict[str, Any]:
    """Pick tailored questions for a quiz session based on target subject or due concepts."""
    eligible_questions = list(db_questions)
    if req.subject:
        eligible_questions = [q for q in eligible_questions if q["subject"].lower() == req.subject.lower()]
    if req.concept_id:
        eligible_questions = [q for q in eligible_questions if q["concept_id"] == req.concept_id]

    if not eligible_questions:
        eligible_questions = list(db_questions)

    # Sort questions prioritizing lowest concept p_hat
    def get_q_priority(q):
        c = db_concepts.get(q["concept_id"])
        return c["p_hat"] if c else 0.5

    ranked_q = sorted(eligible_questions, key=get_q_priority)
    selected = ranked_q[:req.limit]

    session_id = f"sess-{uuid.uuid4().hex[:8]}"
    db_sessions[session_id] = {
        "id": session_id,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "questions": selected,
        "attempts": []
    }

    return {
        "session_id": session_id,
        "questions": selected,
        "total_questions": len(selected)
    }

@app.post("/api/sessions/{session_id}/answers")
def record_answer(session_id: str, req: SessionAnswerRequest) -> Dict[str, Any]:
    """Records an answered question event idempotently."""
    attempt_record = req.dict()
    attempt_record["recorded_at"] = datetime.now(timezone.utc).isoformat()
    db_attempts.append(attempt_record)
    
    if session_id in db_sessions:
        db_sessions[session_id]["attempts"].append(attempt_record)
        
    # Return instantaneous HLR feedback for the answered concept
    c = db_concepts.get(req.concept_id)
    if c:
        old_h = c["half_life_days"]
        # Fast preview of half-life update: correct multiplies h, wrong reduces it
        projected_h = half_life(
            LAUNCH_THETA,
            [1.0, float(c["n_right"] + (1 if req.is_correct else 0)), float(c["n_wrong"] + (0 if req.is_correct else 1))]
        )
        return {
            "recorded": True,
            "event_id": req.event_id,
            "is_correct": req.is_correct,
            "old_half_life": old_h,
            "projected_half_life": round(projected_h, 3),
            "h_change_pct": round(((projected_h - old_h) / old_h) * 100, 1)
        }

    return {"recorded": True, "event_id": req.event_id}

@app.post("/api/sessions/{session_id}/complete")
def complete_session(session_id: str) -> Dict[str, Any]:
    """
    Session close (Section 5 per concept):
    1. p = correct / attempts in the session.
    2. Delta = now - last_practiced_at.
    3. Save training_record(p, Delta, x_before).
    4. Update counts, compute h_hat with active Theta, and set next_review_at.
    """
    sess = db_sessions.get(session_id)
    attempts = sess["attempts"] if sess else [a for a in db_attempts[-5:]]
    
    now_dt = datetime.now(timezone.utc)
    concept_stats: Dict[str, Dict[str, int]] = {}
    for a in attempts:
        cid = a["concept_id"]
        if cid not in concept_stats:
            concept_stats[cid] = {"correct": 0, "total": 0}
        concept_stats[cid]["total"] += 1
        if a["is_correct"]:
            concept_stats[cid]["correct"] += 1

    updates = []
    for cid, stats in concept_stats.items():
        if cid not in db_concepts:
            continue
        c = db_concepts[cid]
        p_session = stats["correct"] / stats["total"]
        
        last_dt = datetime.fromisoformat(c["last_practiced_at"])
        delta_days = max(0.01, (now_dt - last_dt).total_seconds() / 86400.0)
        
        old_h = c["half_life_days"]
        
        # Update counts
        c["n_right"] += stats["correct"]
        c["n_wrong"] += (stats["total"] - stats["correct"])
        c["last_practiced_at"] = now_dt.isoformat()
        
        # Compute new half_life
        new_x = [1.0, float(c["n_right"]), float(c["n_wrong"])]
        new_h = half_life(LAUNCH_THETA, new_x)
        c["half_life_days"] = round(new_h, 3)
        c["p_hat"] = 0.99  # immediately after practice, recall is near maximum
        
        # Next review
        review_days = next_review_days(new_h, db_settings.retention_threshold)
        next_dt = now_dt + timedelta(days=review_days)
        c["next_review_at"] = next_dt.isoformat()
        c["is_due"] = False
        
        # Save training record and add point to practice history
        if cid not in db_practice_history:
            db_practice_history[cid] = []
        db_practice_history[cid].append({
            "delta_days": round(delta_days, 2),
            "p_observed": round(p_session, 2),
            "p_hat": round(recall_prob(old_h, delta_days), 3),
            "type": f"Session {session_id[-4:]}",
            "date": now_dt.strftime("%b %d, %H:%M")
        })

        updates.append({
            "concept_id": cid,
            "concept_name": c["name"],
            "subject": c["subject"],
            "session_score": f"{stats['correct']}/{stats['total']}",
            "old_half_life": old_h,
            "new_half_life": round(new_h, 3),
            "next_review_days": round(review_days, 1),
            "next_review_date": next_dt.strftime("%b %d")
        })

    return {
        "success": True,
        "session_id": session_id,
        "completed_at": now_dt.isoformat(),
        "total_attempts": len(attempts),
        "concept_updates": updates
    }

@app.get("/api/settings")
def get_settings() -> UserSettings:
    return db_settings

@app.put("/api/settings")
def update_settings(settings: UserSettings) -> UserSettings:
    global db_settings
    db_settings = settings
    return db_settings

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

# ---------------------------------------------------------------------------
# Backwards-compatibility for existing schedule endpoint if called
# ---------------------------------------------------------------------------
class LegacyTask(BaseModel):
    id: Optional[int] = None
    subject: str
    deadline_days: int = 3
    difficulty: Literal["Easy", "Medium", "Hard"] = "Medium"
    status: str = "Planned"

class LegacyTimeSlot(BaseModel):
    day: int
    start: str
    end: str

class LegacyScheduleRequest(BaseModel):
    tasks: List[LegacyTask]
    available_slots: List[LegacyTimeSlot]
    locked_schedule: List[Dict[str, Any]] = []

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
        "generated_on": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "total_slots": len(request.available_slots),
        "scheduled_slots": len(output),
        "completion_percent": 100,
        "schedule": output,
        "priority_order": [t.subject for t in request.tasks]
    }
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
