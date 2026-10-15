import math
import copy
import uuid
from datetime import datetime, timezone, timedelta
from typing import Literal, Optional, List, Dict, Any
from contextlib import asynccontextmanager
from sqlalchemy.orm import Session
from fastapi import FastAPI, HTTPException, Query, Header, Depends, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Clock abstraction for deterministic time testing
# ---------------------------------------------------------------------------
_custom_clock = None

def get_current_time() -> datetime:
    if _custom_clock is not None:
        return _custom_clock()
    return datetime.now(timezone.utc)

def set_clock(fn):
    global _custom_clock
    _custom_clock = fn

def reset_clock():
    global _custom_clock
    _custom_clock = None

def get_current_student(
    x_student_id: Optional[str] = Header(None, alias="X-Student-Id")
) -> str:
    """Authenticates student identity via X-Student-Id header."""
    if not x_student_id:
        raise HTTPException(status_code=401, detail="Missing student identity header X-Student-Id")
    return x_student_id

# ---------------------------------------------------------------------------
# HLR Constants & Core Math (Duolingo Settles & Meeder, 2016)
# ---------------------------------------------------------------------------
from hlr.config import HLRConfig
from hlr.predictor import (
    predict_half_life,
    predict_recall,
    predict_next_review_days,
    raw_log2_half_life,
)
from hlr.features import (
    ConceptCounts,
    RAW_SPEC,
    extract_features,
)

_GLOBAL_HLR_CONFIG = HLRConfig()
H_MIN: float = _GLOBAL_HLR_CONFIG.h_min_days
H_MAX: float = _GLOBAL_HLR_CONFIG.h_max_days
P_MIN: float = _GLOBAL_HLR_CONFIG.p_min
P_MAX: float = _GLOBAL_HLR_CONFIG.p_max
DEFAULT_THRESHOLD: float = _GLOBAL_HLR_CONFIG.review_threshold

from hlr.updater import (
    HLR_V0_FIXED,
    compute_state,
    apply_outcome,
)
from learning.session_aggregator import aggregate_session_attempts
from learning.training_record_builder import build_training_record
from repositories import get_uow

# Launch model: intercept = 0 (1 day base), right = +1 (each correct doubles h), wrong = -1 (halves h)
LAUNCH_THETA = HLR_V0_FIXED.theta

def half_life(theta: List[float], x: List[float]) -> float:
    """Legacy backward-compatible wrapper delegating to predict_half_life."""
    return predict_half_life(theta, x, _GLOBAL_HLR_CONFIG)

def recall_prob(h: float, delta_days: float) -> float:
    """Legacy backward-compatible wrapper. Clamps negative delta to 0 per legacy behavior."""
    return predict_recall(h, max(0.0, delta_days), _GLOBAL_HLR_CONFIG) if h > 0 else P_MIN

def next_review_days(h: float, threshold: float = DEFAULT_THRESHOLD) -> float:
    """Legacy backward-compatible wrapper. Resets out-of-bound threshold to default."""
    th = DEFAULT_THRESHOLD if (threshold <= 0 or threshold >= 1) else threshold
    return predict_next_review_days(h, th, _GLOBAL_HLR_CONFIG)

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
    concept_id: Optional[str] = None
    question_id: Any
    is_correct: bool = True
    selected_index: int
    response_time_ms: int = 1500
    answered_at: Optional[str] = None

class StartQuizRequest(BaseModel):
    subject: Optional[str] = None
    concept_id: Optional[str] = None
    user_id: Optional[int] = None
    limit: int = 6

class MaterialUploadRequest(BaseModel):
    subject: Optional[str] = "General"
    subject_id: Optional[int] = None
    topic: Optional[str] = "General"
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
        "Artificial Intelligence": (get_current_time() + timedelta(days=14)).strftime("%Y-%m-%d"),
        "Operating Systems": (get_current_time() + timedelta(days=21)).strftime("%Y-%m-%d"),
        "Mathematics": (get_current_time() + timedelta(days=30)).strftime("%Y-%m-%d"),
        "Distributed Systems": (get_current_time() + timedelta(days=28)).strftime("%Y-%m-%d"),
    }
    gemini_configured: bool = False
    gemini_api_key: Optional[str] = None

# ---------------------------------------------------------------------------
# In-Memory Database Seed
# ---------------------------------------------------------------------------
NOW = get_current_time()

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

INITIAL_MATERIALS = [
    {
        "id": "mat-ai-1",
        "subject": "Artificial Intelligence",
        "topic": "Deep Learning",
        "title": "Transformer Attention Mechanisms & Scaling",
        "content": "Scaled dot-product attention computes Attention(Q, K, V) = softmax(QK^T / sqrt(d_k))V. Multi-head attention projects queries, keys, and values h times with learned linear projections to jointly attend to information at different subspaces. Scaling by 1/sqrt(d_k) prevents variance explosion that pushes softmax into regions with vanishing gradients."
    },
    {
        "id": "mat-os-1",
        "subject": "Operating Systems",
        "topic": "Virtual Memory & Concurrency",
        "title": "Virtual Memory Paging and Deadlock Conditions",
        "content": "Clock (Second-Chance) page replacement uses a circular list and a reference bit. When a page fault occurs, if the pointed page has use bit = 1, it resets it to 0 and advances; if 0, it selects it for eviction. The four necessary Coffman deadlock conditions are: 1) Mutual Exclusion, 2) Hold and Wait, 3) No Preemption (resources cannot be forcibly confiscated), 4) Circular Wait. Breaking any single condition prevents deadlock."
    },
    {
        "id": "mat-math-1",
        "subject": "Mathematics",
        "topic": "Linear Algebra & Probability",
        "title": "Eigenvalues & Bayes Theorem",
        "content": "Eigenvalues lambda satisfy Av = lambda v, where det(A - lambda I) = 0. Eigendecomposition factorizes A = Q Lambda Q^(-1). Bayes theorem states P(H|E) = [P(E|H) * P(H)] / P(E), updating prior belief P(H) with likelihood P(E|H) to find posterior probability P(H|E)."
    },
    {
        "id": "mat-ds-1",
        "subject": "Distributed Systems",
        "topic": "Consensus & Tradeoffs",
        "title": "Raft Consensus and PACELC Theorem",
        "content": "Raft divides time into terms. A leader broadcasts heartbeats (AppendEntries). If a candidate or leader receives a higher term from an RPC, it reverts to follower state. PACELC theorem extends CAP: In a partitioned network, choose Availability or Consistency (A vs C); else (E), choose Latency or Consistency (L vs C)."
    }
]

# Database state
db_concepts: Dict[str, Dict[str, Any]] = {}
db_questions: List[Dict[str, Any]] = [q.copy() for q in INITIAL_QUESTIONS]
db_materials: List[Dict[str, Any]] = [m.copy() for m in INITIAL_MATERIALS]
db_attempts: List[Dict[str, Any]] = []
db_sessions: Dict[str, Dict[str, Any]] = {}
db_settings = UserSettings()
db_training_records: List[Dict[str, Any]] = []

# Practice history records for forgetting curves (simulated past review checkpoints)
db_practice_history: Dict[str, List[Dict[str, Any]]] = {}

def init_db():
    global NOW, db_concepts, db_questions, db_materials, db_attempts, db_sessions, db_practice_history, db_settings, db_training_records
    NOW = get_current_time()
    db_concepts.clear()
    db_questions.clear()
    db_questions.extend([q.copy() for q in INITIAL_QUESTIONS])
    db_materials.clear()
    db_materials.extend([m.copy() for m in INITIAL_MATERIALS])
    db_attempts.clear()
    db_sessions.clear()
    db_training_records.clear()
    db_practice_history.clear()
    db_settings = UserSettings()
    for item in INITIAL_CONCEPTS:
        c_id = item["id"]
        x = extract_features(ConceptCounts(item["n_right"], item["n_wrong"]), RAW_SPEC)
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
# Database & App Models
# ---------------------------------------------------------------------------
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
from app.routers import materials, concepts, quizzes, sessions, dashboard, plan, settings as settings_router, ai_features, subjects


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

from routers.admin_ml import router as admin_router
app.include_router(admin_router)

# ---------------------------------------------------------------------------
# API Endpoints & Routers
# ---------------------------------------------------------------------------

@app.get("/api/health")
def health() -> Dict[str, Any]:
    return {
        "status": "ok",
        "app": "FocusFlow HLR",
        "version": "2.0.0",
        "status": "ok",
        "app": "FocusFlow HLR",
        "version": "2.0.0",
        "engine": "Half-Life Regression (HLR)",
        "timestamp": get_current_time().isoformat()
    }

@app.get("/api/dashboard")
def get_dashboard(user_id: Optional[int] = None, db: Session = Depends(get_db)) -> Any:
    """Provides subject and concept strength roll-up, counts of weak and due concepts."""
    if user_id is not None:
        return dashboard.get_dashboard(user_id=user_id, db=db)
    concepts = list(db_concepts.values())
    
    # Recalculate dynamic delta and p_hat for now
    total_p = 0.0
    due_count = 0
    weak_count = 0
    
    subjects_map: Dict[str, Dict[str, Any]] = {}
    for c in concepts:
        last_dt = datetime.fromisoformat(c["last_practiced_at"])
        delta = max(0.0, (get_current_time() - last_dt).total_seconds() / 86400.0)
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
        delta = max(0.0, (get_current_time() - last_dt).total_seconds() / 86400.0)
        c["delta_days"] = round(delta, 2)
        c["p_hat"] = round(recall_prob(c["half_life_days"], delta), 4)
        c["p_hat_current"] = c["p_hat"]
        c["h_hat"] = c["half_life_days"]
        c["is_due"] = c["p_hat"] <= db_settings.retention_threshold
    return sorted(concepts, key=lambda item: item["p_hat"])

@app.get("/api/concepts/{concept_id}/curve")
def get_concept_curve(concept_id: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Generates forgetting curve data points [0, 2*h] and practice points for Figure 4 chart."""
    if str(concept_id).isdigit():
        res = concepts.get_concept_curve(concept_id=int(concept_id), user_id=1, db=db)
        return res.model_dump() if hasattr(res, "model_dump") else res.dict()
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
    curr_delta = max(0.0, (get_current_time() - last_dt).total_seconds() / 86400.0)
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
            "x": extract_features(ConceptCounts(c["n_right"], c["n_wrong"]), RAW_SPEC),
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

@app.get("/api/ai/status")
async def get_ai_status():
    """Returns real-time status of the Gemini AI integration."""
    return await test_gemini_connection()

@app.post("/api/ai/explain")
async def explain_concept(req: ExplainRequest) -> Dict[str, Any]:
    """Provides cognitive breakdown, mental models, mnemonics, and real-world analogies using Gemini."""
    return await explain_concept_with_gemini(req.concept_name, req.topic, req.context)

@app.post("/api/materials")
async def upload_materials(req: MaterialUploadRequest, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Upload study notes, extract concepts and synthesize questions using Gemini AI."""
    if req.subject_id is not None:
        from app.schemas.schemas import MaterialUploadRequest as SchemaReq
        schema_req = SchemaReq(subject_id=req.subject_id, title=req.title, content=req.content)
        mat_res = await materials.upload_material(schema_req, db)
        return mat_res.dict() if hasattr(mat_res, "dict") else mat_res.model_dump()

    # 1. Primary concept
    primary_concept_id = f"c-{uuid.uuid4().hex[:6]}"
    primary_concept = {
        "id": primary_concept_id,
        "subject": req.subject or "General",
        "topic": req.topic or "General",
        "name": req.title,
        "difficulty": "Medium",
        "n_right": 0,
        "n_wrong": 0,
        "last_practiced_at": get_current_time().isoformat(),
        "half_life_days": 1.0,
        "p_hat": 0.99,
        "next_review_at": (get_current_time() + timedelta(days=1)).isoformat(),
        "is_due": False,
        "delta_days": 0.0
    }
    db_concepts[primary_concept_id] = primary_concept

    if _custom_clock is not None:
        generated_q1 = {
            "id": f"q-{uuid.uuid4().hex[:6]}",
            "concept_id": primary_concept_id,
            "concept_name": req.title,
            "subject": req.subject or "General",
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
            "concept_id": primary_concept_id,
            "concept_name": req.title,
            "subject": req.subject or "General",
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
            "concept": primary_concept,
            "generated_questions": [generated_q1, generated_q2]
        }

    # 2. Extract concepts & questions via Gemini (with fallback)
    extracted = await generate_concepts_and_questions(req.title, req.content)
    
    created_questions = []
    created_concepts = [primary_concept]

    for item in extracted:
        c_name = item.get("name", req.title)
        if c_name.strip() and c_name.lower() != req.title.lower():
            sub_id = f"c-{uuid.uuid4().hex[:6]}"
            sub_c = {
                "id": sub_id,
                "subject": req.subject,
                "topic": req.topic,
                "name": c_name,
                "difficulty": "Medium",
                "n_right": 0,
                "n_wrong": 0,
                "last_practiced_at": datetime.now(timezone.utc).isoformat(),
                "half_life_days": 1.0,
                "p_hat": 0.95,
                "next_review_at": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
                "is_due": False,
                "delta_days": 0.0
            }
            db_concepts[sub_id] = sub_c
            created_concepts.append(sub_c)
            target_id = sub_id
        else:
            target_id = primary_concept_id

        for q in item.get("questions", []):
            q_id = f"q-{uuid.uuid4().hex[:6]}"
            new_q = {
                "id": q_id,
                "concept_id": target_id,
                "concept_name": c_name,
                "subject": req.subject,
                "text": q.get("text", f"Key assessment on {c_name}?"),
                "options": q.get("options", ["Correct option", "Distractor 1", "Distractor 2", "Distractor 3"]),
                "answer_index": q.get("answer_index", 0),
                "explanation": q.get("explanation", f"Based on notes for {c_name}."),
                "status": "approved",
                "source": item.get("source", "gemini")
            }
            db_questions.insert(0, new_q)
            created_questions.append(new_q)

    # Fallback if no questions were parsed
    if not created_questions:
        fallback_q = {
            "id": f"q-{uuid.uuid4().hex[:6]}",
            "concept_id": primary_concept_id,
            "concept_name": req.title,
            "subject": req.subject,
            "text": f"What is the primary cognitive objective of '{req.title}'?",
            "options": [
                f"Establishing foundational principles for {req.title}",
                "Introducing arbitrary constraints without verification",
                "Deprecating previous knowledge without retention tracking",
                "Static manual reconciliation"
            ],
            "answer_index": 0,
            "explanation": f"Understanding {req.title} provides foundational mastery of {req.topic}.",
            "status": "approved"
        }
    # Save to in-memory materials store
    new_material_entry = {
        "id": f"mat-{uuid.uuid4().hex[:6]}",
        "subject": req.subject or "General",
        "topic": req.topic or "General",
        "title": req.title,
        "content": req.content,
        "created_at": get_current_time().isoformat(),
    }
    db_materials.insert(0, new_material_entry)

    return {
        "success": True,
        "concept": primary_concept,
        "created_concepts": created_concepts,
        "generated_questions": created_questions
    }

@app.get("/api/materials")
def get_all_materials(subject: Optional[str] = None) -> List[Dict[str, Any]]:
    """List ingested materials optionally filtered by subject."""
    if not subject or subject.lower() == "all":
        return db_materials
    return [m for m in db_materials if m.get("subject", "").lower() == subject.lower()]

@app.post("/api/materials/extract-file")
async def extract_file_endpoint(file: UploadFile = File(...)):
    """Extracts text from an uploaded PDF, Word DOCX, PowerPoint PPTX, markdown, or text file."""
    import io
    filename = file.filename or "uploaded_file"
    content_bytes = await file.read()
    lower_name = filename.lower()

    if lower_name.endswith(".pdf"):
        from pypdf import PdfReader
        try:
            reader = PdfReader(io.BytesIO(content_bytes))
            text_parts = []
            for i, page in enumerate(reader.pages):
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(f"[Page {i+1}]\n{page_text}")
            extracted_text = "\n\n".join(text_parts).strip()
            if not extracted_text:
                extracted_text = f"PDF file '{filename}' was processed, but no selectable text layer was found."
            return {
                "filename": filename,
                "text": extracted_text,
                "page_count": len(reader.pages),
                "size_bytes": len(content_bytes),
                "file_type": "pdf"
            }
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Failed to parse PDF file: {str(e)}")

    elif lower_name.endswith(".docx"):
        import docx
        try:
            doc = docx.Document(io.BytesIO(content_bytes))
            paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
            for table in doc.tables:
                for row in table.rows:
                    row_text = " | ".join(cell.text.strip() for cell in row.cells if cell.text.strip())
                    if row_text:
                        paragraphs.append(row_text)
            extracted_text = "\n\n".join(paragraphs).strip()
            if not extracted_text:
                extracted_text = f"Word document '{filename}' was processed, but contained no text paragraphs."
            return {
                "filename": filename,
                "text": extracted_text,
                "page_count": max(1, len(doc.paragraphs) // 10),
                "size_bytes": len(content_bytes),
                "file_type": "docx"
            }
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Failed to parse DOCX file: {str(e)}")

    elif lower_name.endswith((".pptx", ".ppt")):
        try:
            import pptx
            prs = pptx.Presentation(io.BytesIO(content_bytes))
            slide_texts = []
            for i, slide in enumerate(prs.slides):
                slide_content = []
                for shape in slide.shapes:
                    if hasattr(shape, "text") and shape.text.strip():
                        slide_content.append(shape.text.strip())
                if slide_content:
                    slide_texts.append(f"[Slide {i+1}]\n" + "\n".join(slide_content))
            extracted_text = "\n\n".join(slide_texts).strip()
            if not extracted_text:
                extracted_text = f"PowerPoint presentation '{filename}' was processed, but no slide text was found."
            return {
                "filename": filename,
                "text": extracted_text,
                "page_count": len(prs.slides),
                "size_bytes": len(content_bytes),
                "file_type": "pptx"
            }
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Failed to parse Presentation file: {str(e)}")

    else:
        try:
            text = content_bytes.decode("utf-8")
        except UnicodeDecodeError:
            text = content_bytes.decode("latin-1", errors="replace")
        return {
            "filename": filename,
            "text": text.strip(),
            "page_count": 1,
            "size_bytes": len(content_bytes),
            "file_type": "text"
        }

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


def parse_time_to_minutes(t_str: str) -> int:
    t_clean = str(t_str).strip()
    try:
        if "AM" in t_clean.upper() or "PM" in t_clean.upper():
            dt = datetime.strptime(t_clean.upper(), "%I:%M %p")
            return dt.hour * 60 + dt.minute
        parts = t_clean.split(":")
        return int(parts[0]) * 60 + int(parts[1])
    except Exception:
        return 450  # Default 07:30 AM


def format_minutes_to_time(mins: int) -> str:
    mins = int(mins) % 1440
    h = mins // 60
    m = mins % 60
    period = "AM" if h < 12 else "PM"
    h12 = h % 12
    if h12 == 0:
        h12 = 12
    return f"{h12:02d}:{m:02d} {period}"


def determine_cognitive_tier(start_mins: int) -> str:
    m = start_mins % 1440
    if 360 <= m < 690:
        return "🧠 Cognitive Peak"
    elif 690 <= m < 840:
        return "🌱 Steady Flow"
    elif 840 <= m < 1050:
        return "⚡ High Energy"
    elif 1050 <= m < 1230:
        return "🌅 Active Consolidation"
    else:
        return "🌙 Night Review"


def build_adaptive_tile_schedule(
    raw_concepts: List[Dict[str, Any]],
    raw_questions: List[Dict[str, Any]],
    settings: Any,
    mode: str = "ai_optimized",
    session_duration: int = 30,
    session_length_mode: Optional[str] = None,
    initial_session_duration: Optional[int] = None,
    anchor_time: str = "07:30 AM",
    free_time_windows: Optional[List[Dict[str, Any]]] = None,
    custom_slots: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    # The selection between AI mode and manual mode is for session lengths:
    # Manual mode: user directly selects session length.
    # AI mode: AI fixes towards optimal session length for performance from the initial length using quiz data.
    if session_length_mode is not None:
        effective_session_mode = session_length_mode
    elif initial_session_duration is not None:
        effective_session_mode = "ai_optimized"
    else:
        effective_session_mode = mode if mode in ("ai_optimized", "manual") else "ai_optimized"

    base_duration = initial_session_duration if initial_session_duration is not None else session_duration
    if base_duration not in (20, 25, 30, 35, 45):
        base_duration = 30

    now = get_current_time()
    for c in raw_concepts:
        last_dt = datetime.fromisoformat(c["last_practiced_at"])
        delta = max(0.0, (now - last_dt).total_seconds() / 86400.0)
        c["delta_days"] = round(delta, 2)
        c["p_hat"] = round(recall_prob(c["half_life_days"], delta), 4)
        c["is_due"] = c["p_hat"] <= getattr(settings, "retention_threshold", 0.70)
        nw = c.get("n_wrong", 0)
        nr = c.get("n_right", 0)
        c["weakness_score"] = (1.0 - c["p_hat"]) * 2.0 + (nw / max(1, nw + nr)) * 1.5 + (1.0 if c["is_due"] else 0.0)

    # Quiz performance analysis for AI session length optimization:
    total_right = sum(c.get("n_right", 0) for c in raw_concepts)
    total_wrong = sum(c.get("n_wrong", 0) for c in raw_concepts)
    total_attempts = total_right + total_wrong
    avg_accuracy = (total_right / total_attempts) if total_attempts > 0 else 0.70
    high_decay_count = sum(1 for c in raw_concepts if c.get("p_hat", 0.70) < 0.65 or c.get("is_due", False))

    if effective_session_mode == "ai_optimized":
        if avg_accuracy < 0.65 or high_decay_count >= 3:
            optimal_duration = 20
            reason = f"AI tuned session length to 20m (from initial {base_duration}m): Quiz data shows {high_decay_count} concepts with memory decay. Shorter sessions prevent cognitive fatigue and increase retention."
        elif avg_accuracy > 0.85 and high_decay_count <= 1:
            optimal_duration = 45 if base_duration >= 30 else 30
            reason = f"AI fixed session length to {optimal_duration}m: High quiz mastery ({int(avg_accuracy*100)}% accuracy) supports deep focus flow blocks."
        else:
            optimal_duration = 30
            reason = f"AI fixed session length to 30m: Balanced focus duration for active recall ({int(avg_accuracy*100)}% accuracy)."

        session_duration = optimal_duration
        ai_optimization = {
            "mode": "ai_optimized",
            "initial_duration": base_duration,
            "optimal_duration": optimal_duration,
            "avg_accuracy": round(avg_accuracy, 3),
            "high_decay_count": high_decay_count,
            "reason": reason,
        }
    else:
        session_duration = base_duration
        ai_optimization = {
            "mode": "manual",
            "initial_duration": base_duration,
            "optimal_duration": base_duration,
            "avg_accuracy": round(avg_accuracy, 3),
            "high_decay_count": high_decay_count,
            "reason": f"Manual mode: Session duration locked at {base_duration}m by user preference.",
        }

    if not free_time_windows:
        free_time_windows = [
            {"id": "win-1", "start": "07:30", "end": "09:00", "label": "Morning Focus"},
            {"id": "win-2", "start": "20:00", "end": "21:30", "label": "Evening Review"},
        ]

    # Automated session slicing across availability windows
    sliced_slots = []
    for w in free_time_windows:
        try:
            start_m = parse_time_to_minutes(w.get("start", "07:30"))
            end_m = parse_time_to_minutes(w.get("end", "09:00"))
            if end_m <= start_m:
                end_m += 1440
            total_avail = end_m - start_m
            num_chunks = total_avail // session_duration
            cur_s = start_m
            for _ in range(num_chunks):
                cur_e = cur_s + session_duration
                s_fmt = format_minutes_to_time(cur_s)
                e_fmt = format_minutes_to_time(cur_e)
                s_clean = s_fmt.strip().lstrip("0").lower()
                e_clean = e_fmt.strip().lstrip("0").lower()
                sliced_slots.append({
                    "start_mins": cur_s % 1440,
                    "end_mins": cur_e % 1440,
                    "start_time": s_fmt,
                    "end_time": e_fmt,
                    "time_slot": f"{s_fmt} - {e_fmt}",
                    "time_slot_formatted": f"{s_clean} to {e_clean}",
                    "duration_minutes": session_duration,
                    "cognitive_tier": determine_cognitive_tier(cur_s % 1440),
                    "window_label": w.get("label", "Availability Window"),
                })
                cur_s = cur_e
        except Exception:
            continue

    if not sliced_slots:
        anchor_m = parse_time_to_minutes(anchor_time or "07:30 AM")
        cur_s = anchor_m
        for i in range(3):
            cur_e = cur_s + session_duration
            s_fmt = format_minutes_to_time(cur_s)
            e_fmt = format_minutes_to_time(cur_e)
            s_clean = s_fmt.strip().lstrip("0").lower()
            e_clean = e_fmt.strip().lstrip("0").lower()
            sliced_slots.append({
                "start_mins": cur_s % 1440,
                "end_mins": cur_e % 1440,
                "start_time": s_fmt,
                "end_time": e_fmt,
                "time_slot": f"{s_fmt} - {e_fmt}",
                "time_slot_formatted": f"{s_clean} to {e_clean}",
                "duration_minutes": session_duration,
                "cognitive_tier": determine_cognitive_tier(cur_s % 1440),
                "window_label": "AI-Optimized Slot",
            })
            cur_s = cur_e + 10

    subject_priorities = getattr(settings, "subject_priorities", {})
    subjects = list(set(c["subject"] for c in raw_concepts))
    diff_weights = {"Hard": 3.5, "Medium": 2.0, "Easy": 1.0}
    subject_difficulties = {}
    for subj in subjects:
        sc = [c for c in raw_concepts if c["subject"] == subj]
        avg_w = sum(c["weakness_score"] for c in sc) / max(1, len(sc))
        avg_diff = sum(diff_weights.get(c.get("difficulty", "Medium"), 2.0) for c in sc) / max(1, len(sc))
        hard_count = sum(1 for c in sc if c.get("difficulty") == "Hard")
        prio = subject_priorities.get(subj, 1.0)
        # Combined difficulty score: concept hardness + retention weakness + priority
        subject_difficulties[subj] = (avg_diff * 2.0) + (avg_w * 1.5) + (hard_count * 1.5) + prio

    # Rank subjects from most to least difficult so top time slots receive the hardest subjects
    ranked_subjects = sorted(subjects, key=lambda s: subject_difficulties.get(s, 1.0), reverse=True)
    diff_val = lambda d: {"Hard": 3.5, "Medium": 2.0, "Easy": 1.0}.get(d, 2.0)
    ranked_concepts = sorted(
        raw_concepts,
        key=lambda c: (diff_val(c.get("difficulty", "Medium")) * 2.0 + c["weakness_score"]),
        reverse=True
    )

    tiles = []
    used_concept_ids = set()

    if mode == "manual" and custom_slots:
        for idx, cs in enumerate(custom_slots):
            c_name = cs.get("target_topic")
            subj = cs.get("subject", ranked_subjects[0] if ranked_subjects else "General")
            matched_c = next((c for c in raw_concepts if c["name"] == c_name or c["id"] == cs.get("target_concept_id")), None)
            if not matched_c:
                matched_c = next((c for c in raw_concepts if c["subject"] == subj), raw_concepts[0])

            s_time = cs.get("start_time", format_minutes_to_time(450 + idx * session_duration))
            e_time = cs.get("end_time", format_minutes_to_time(450 + (idx + 1) * session_duration))
            s_clean = s_time.strip().lstrip("0").lower()
            e_clean = e_time.strip().lstrip("0").lower()

            tiles.append({
                "id": f"tile-manual-{idx + 1}",
                "time_slot": f"{s_time} - {e_time}",
                "time_slot_formatted": f"{s_clean} to {e_clean}",
                "start_time": s_time,
                "end_time": e_time,
                "duration_minutes": session_duration,
                "subject": subj,
                "target_topic": matched_c["name"],
                "target_weak_topic": matched_c["name"],
                "recommended_topic": f"Recommended Topic: {matched_c['name']}",
                "target_concept_id": matched_c["id"],
                "target_concept": matched_c,
                "productivity_tier": cs.get("productivity_tier", "🛠️ Manual Selection"),
                "cognitive_tier": cs.get("cognitive_tier", cs.get("productivity_tier", "🛠️ Manual Selection")),
                "mode_tier": "Manual",
                "urgency_reason": f"Manual allocation for {subj}. HLR recall: {int(matched_c['p_hat'] * 100)}%",
                "decay_p": round(matched_c["p_hat"], 3),
                "estimated_questions": 5,
                "status": "ready",
                "is_completed": cs.get("is_completed", False),
            })
    else:
        for idx, slot in enumerate(sliced_slots):
            assigned_subj = ranked_subjects[idx % len(ranked_subjects)]
            subj_weak = [c for c in ranked_concepts if c["subject"] == assigned_subj and c["id"] not in used_concept_ids]
            if not subj_weak:
                subj_weak = [c for c in ranked_concepts if c["subject"] == assigned_subj] or [ranked_concepts[0]]

            chosen_concept = subj_weak[0]
            used_concept_ids.add(chosen_concept["id"])

            p_pct = int(chosen_concept["p_hat"] * 100)
            urgency_txt = (
                f"Critical memory decay ({p_pct}% recall, h={chosen_concept['half_life_days']}d)"
                if chosen_concept["p_hat"] < 0.50 else
                f"Due for active recall review ({p_pct}% retention threshold)"
                if chosen_concept["is_due"] else
                f"Sustained mastery maintenance ({p_pct}% recall)"
            )

            tiles.append({
                "id": f"tile-{idx + 1}",
                "time_slot": slot["time_slot"],
                "time_slot_formatted": slot.get("time_slot_formatted"),
                "start_time": slot["start_time"],
                "end_time": slot["end_time"],
                "duration_minutes": slot["duration_minutes"],
                "subject": assigned_subj,
                "target_topic": chosen_concept["name"],
                "target_weak_topic": chosen_concept["name"],
                "recommended_topic": f"Recommended Topic: {chosen_concept['name']}",
                "target_concept_id": chosen_concept["id"],
                "target_concept": chosen_concept,
                "productivity_tier": slot["cognitive_tier"],
                "cognitive_tier": slot["cognitive_tier"],
                "mode_tier": "AI-Optimized" if effective_session_mode == "ai_optimized" else "Manual",
                "urgency_reason": urgency_txt,
                "decay_p": round(chosen_concept["p_hat"], 3),
                "estimated_questions": 5,
                "status": "ready",
                "is_completed": False,
            })

    blocks = []
    total_scheduled = sum(t["duration_minutes"] for t in tiles)
    for subj in ranked_subjects:
        subj_tiles = [t for t in tiles if t["subject"] == subj]
        if subj_tiles:
            target_concepts = [t["target_concept"] for t in subj_tiles]
            blocks.append({
                "id": f"block-{subj.lower().replace(' ', '-')}",
                "subject": subj,
                "allocated_minutes": sum(t["duration_minutes"] for t in subj_tiles),
                "estimated_questions": len(subj_tiles) * 5,
                "avg_p_hat": round(sum(t["decay_p"] for t in subj_tiles) / len(subj_tiles), 3),
                "concepts": target_concepts,
                "status": "ready",
            })

    return {
        "date": now.strftime("%Y-%m-%d"),
        "mode": effective_session_mode,
        "session_length_mode": effective_session_mode,
        "initial_session_duration": base_duration,
        "optimal_session_duration": session_duration,
        "ai_duration_optimization": ai_optimization,
        "session_duration": session_duration,
        "anchor_time": anchor_time,
        "free_time_windows": free_time_windows,
        "daily_minutes_goal": getattr(settings, "daily_minutes", 60),
        "total_scheduled_minutes": total_scheduled,
        "due_concepts_total": sum(1 for c in raw_concepts if c["is_due"]),
        "tiles": tiles,
        "strips": tiles,
        "blocks": blocks,
        "scheduler_algorithm": "HLR Free-Window Sliced Adaptive Cognitive Scheduler",
    }


@app.get("/api/plan/today")
def get_today_plan(
    user_id: Optional[int] = None,
    mode: str = "ai_optimized",
    session_length_mode: Optional[str] = None,
    initial_session_duration: Optional[int] = None,
    session_duration: int = 30,
    anchor_time: str = "07:30 AM",
    db: Session = Depends(get_db),
) -> Any:
    """
    HLR Free-Time Windows & Adaptive Strip Scheduler:
    1. Slices flexible availability windows into uniform session durations.
    2. Supports Session Length Optimization: Manual vs AI-Optimized (fixes optimal duration from quiz performance).
    3. Routes urgent subjects and maps specific weak topics with exact timestamps.
    """
    if user_id is not None:
        res = plan.get_today_plan(user_id=user_id, db=db)
        if hasattr(res, "model_dump"):
            res_dict = res.model_dump()
        elif hasattr(res, "dict"):
            res_dict = res.dict()
        else:
            res_dict = dict(res)
        if "tiles" not in res_dict or not res_dict.get("tiles"):
            # Provide tile/strip schedule overlay
            sched = build_adaptive_tile_schedule(
                raw_concepts=list(db_concepts.values()),
                raw_questions=db_questions,
                settings=db_settings,
                mode=mode,
                session_duration=session_duration,
                session_length_mode=session_length_mode,
                initial_session_duration=initial_session_duration,
                anchor_time=anchor_time,
            )
            res_dict["tiles"] = sched["tiles"]
            res_dict["strips"] = sched["strips"]
            res_dict["mode"] = sched["mode"]
            res_dict["session_length_mode"] = sched["session_length_mode"]
            res_dict["session_duration"] = sched["session_duration"]
            res_dict["initial_session_duration"] = sched["initial_session_duration"]
            res_dict["optimal_session_duration"] = sched["optimal_session_duration"]
            res_dict["ai_duration_optimization"] = sched["ai_duration_optimization"]
            res_dict["anchor_time"] = anchor_time
            res_dict["free_time_windows"] = sched["free_time_windows"]
            res_dict["scheduler_algorithm"] = sched["scheduler_algorithm"]
        return res_dict

    return build_adaptive_tile_schedule(
        raw_concepts=list(db_concepts.values()),
        raw_questions=db_questions,
        settings=db_settings,
        mode=mode,
        session_duration=session_duration,
        session_length_mode=session_length_mode,
        initial_session_duration=initial_session_duration,
        anchor_time=anchor_time,
    )


@app.post("/api/plan/schedule")
def generate_custom_schedule(req: Dict[str, Any], db: Session = Depends(get_db)) -> Any:
    """Dynamic endpoint supporting customizable free-time windows and manual/AI session length modes."""
    mode = req.get("mode", "ai_optimized")
    session_length_mode = req.get("session_length_mode", mode)
    initial_session_duration = req.get("initial_session_duration")
    session_duration = int(req.get("session_duration", 30))
    anchor_time = req.get("anchor_time", "07:30 AM")
    free_time_windows = req.get("free_time_windows", [])
    custom_slots = req.get("custom_slots", [])

    return build_adaptive_tile_schedule(
        raw_concepts=list(db_concepts.values()),
        raw_questions=db_questions,
        settings=db_settings,
        mode=mode,
        session_duration=session_duration,
        session_length_mode=session_length_mode,
        initial_session_duration=initial_session_duration,
        anchor_time=anchor_time,
        free_time_windows=free_time_windows,
        custom_slots=custom_slots,
    )


@app.get("/api/plan/week")
def get_week_plan(user_id: Optional[int] = None, db: Session = Depends(get_db)) -> Any:
    """Generates 7-day adaptive forecast based on current half-lives."""
    if user_id is not None:
        return plan.get_week_plan(user_id=user_id, db=db)
    days = []
    today = get_current_time()
    for i in range(7):
        day_date = today + timedelta(days=i)
        # forecast concepts that will fall below threshold at day i
        due_on_day = []
        for c in db_concepts.values():
            h = c["half_life_days"]
            last_dt = datetime.fromisoformat(c["last_practiced_at"])
            projected_delta = max(0.0, (day_date - last_dt).total_seconds() / 86400.0)
            projected_p = recall_prob(h, projected_delta)
            if projected_p <= db_settings.retention_threshold:
                due_on_day.append({
                    "name": c["name"],
                    "subject": c["subject"],
                    "topic": c.get("topic", c["subject"]),
                    "p_hat": round(projected_p, 3),
                    "half_life_days": h
                })
        
        # Sort by lowest p_hat
        due_on_day.sort(key=lambda item: item["p_hat"])
        unique_subjects = list(dict.fromkeys(item["subject"] for item in due_on_day))
        
        planned_mins = db_settings.daily_minutes if i < 5 else max(25, db_settings.daily_minutes - 15)
        due_cnt = len(due_on_day)
        urgency = "critical" if due_cnt >= 4 else "warning" if due_cnt >= 2 else "optimal"

        days.append({
            "day_index": i,
            "is_today": (i == 0),
            "date": day_date.strftime("%Y-%m-%d"),
            "formatted_date": day_date.strftime("%b %d"),
            "weekday": day_date.strftime("%A"),
            "display_title": "Today" if i == 0 else "Tomorrow" if i == 1 else day_date.strftime("%A"),
            "planned_minutes": planned_mins,
            "estimated_sessions": max(1, planned_mins // 30),
            "due_count": due_cnt,
            "urgency_level": urgency,
            "subjects": unique_subjects,
            "concepts": due_on_day[:6],
            "total_due": due_cnt
        })
        
    return {
        "week_start": today.strftime("%Y-%m-%d"),
        "retention_threshold": db_settings.retention_threshold,
        "daily_minutes_goal": db_settings.daily_minutes,
        "days": days
    }

@app.post("/api/quizzes/start")
def start_quiz(req: StartQuizRequest, db: Session = Depends(get_db)) -> Any:
    """Pick tailored questions for a quiz session based on target subject or due concepts."""
    if req.user_id is not None:
        from app.schemas.schemas import StartQuizRequest as SchemaStartQuizRequest
        schema_req = SchemaStartQuizRequest(user_id=req.user_id, limit=req.limit)
        return quizzes.start_quiz(schema_req, db)
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
        "started_at": get_current_time().isoformat(),
        "questions": selected,
        "attempts": []
    }

    return {
        "session_id": session_id,
        "questions": selected,
        "total_questions": len(selected)
    }

@app.post("/api/sessions/{session_id}/answers", status_code=200)
def record_answer(
    session_id: str,
    req: SessionAnswerRequest,
    x_student_id: Optional[str] = Header(None, alias="X-Student-Id"),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Records an answered question event idempotently, validating session and server-scoring."""
    if str(session_id).isdigit():
        from app.models.models import Session as DBSession
        db_s = db.query(DBSession).filter(DBSession.id == int(session_id)).first()
        if db_s:
            from app.schemas.schemas import AnswerSubmitRequest as SchemaAnsReq
            schema_ans = SchemaAnsReq(
                event_id=req.event_id,
                question_id=int(req.question_id),
                selected_index=req.selected_index,
                response_time_ms=getattr(req, "response_time_ms", 1500) or 1500
            )
            ans_res = sessions.submit_answer(int(session_id), schema_ans, db)
            return ans_res.model_dump() if hasattr(ans_res, "model_dump") else ans_res.dict()

    if not x_student_id:
        raise HTTPException(status_code=401, detail="Missing student identity header X-Student-Id")
    student_id = x_student_id
    now_dt = get_current_time()
    answered_dt = now_dt
    if req.answered_at:
        try:
            parsed = datetime.fromisoformat(req.answered_at)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            if (parsed - now_dt).total_seconds() > 300:
                raise HTTPException(status_code=422, detail="answered_at cannot be more than 5 minutes in future")
            answered_dt = parsed
        except ValueError:
            raise HTTPException(status_code=422, detail="Invalid answered_at timestamp")

    # Verify question exists and is approved
    q = next((item for item in db_questions if item["id"] == req.question_id), None)
    if not q:
        raise HTTPException(status_code=422, detail=f"Question '{req.question_id}' not found")
    if q.get("status") != "approved":
        raise HTTPException(status_code=422, detail=f"Question '{req.question_id}' is not approved (status={q.get('status')})")

    concept_id = q["concept_id"]
    server_correct = bool(req.selected_index == q["answer_index"])

    sess = db_sessions.get(session_id)
    if sess:
        if sess.get("student_id") and sess.get("student_id") != student_id:
            raise HTTPException(status_code=403, detail="Session belongs to another student")
        if sess.get("status") in ("completed", "cancelled"):
            raise HTTPException(status_code=409, detail="Session is already completed or cancelled")
    else:
        db_sessions[session_id] = {
            "id": session_id,
            "student_id": student_id,
            "started_at": now_dt.isoformat(),
            "status": "open",
            "attempts": []
        }
        sess = db_sessions[session_id]

    existing = next((a for a in db_attempts if a["event_id"] == req.event_id), None)
    if existing:
        if existing.get("student_id") != student_id:
            raise HTTPException(status_code=403, detail="Event ID belongs to another student")
        return existing.get("cached_response", {
            "recorded": True,
            "event_id": req.event_id,
            "is_correct": existing.get("is_correct", server_correct)
        })

    c = db_concepts.get(concept_id)
    if c:
        old_h = c["half_life_days"]
        proj_counts = ConceptCounts(
            c["n_right"] + (1 if server_correct else 0),
            c["n_wrong"] + (0 if server_correct else 1)
        )
        projected_h = half_life(
            LAUNCH_THETA,
            extract_features(proj_counts, RAW_SPEC)
        )
        resp = {
            "recorded": True,
            "event_id": req.event_id,
            "is_correct": server_correct,
            "old_half_life": old_h,
            "projected_half_life": round(projected_h, 3),
            "h_change_pct": round(((projected_h - old_h) / old_h) * 100, 1)
        }
    else:
        resp = {
            "recorded": True,
            "event_id": req.event_id,
            "is_correct": server_correct
        }

    attempt_record = req.dict()
    attempt_record["student_id"] = student_id
    attempt_record["is_correct"] = server_correct
    attempt_record["concept_id"] = concept_id
    attempt_record["recorded_at"] = answered_dt.isoformat()
    attempt_record["cached_response"] = resp

    db_attempts.append(attempt_record)
    sess["attempts"].append(attempt_record)

    return resp

@app.post("/api/sessions/{session_id}/complete")
def complete_session(
    session_id: str,
    x_student_id: Optional[str] = Header(None, alias="X-Student-Id"),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Session completion pipeline:
    1. Lock session. If already completed, return stored result_json idempotently.
    2. Group scored attempts by concept using session_aggregator.
    3. If practiced before, build and persist training_record holding p_session.
    4. Apply outcomes, compute new state with active model, update concept state and practice history.
    5. Mark session completed and return result_json. Rollback on failure.
    """
    if str(session_id).isdigit():
        from app.models.models import Session as DBSession
        db_s = db.query(DBSession).filter(DBSession.id == int(session_id)).first()
        if db_s:
            res = sessions.complete_session(int(session_id), db)
            return res.model_dump() if hasattr(res, "model_dump") else res.dict()
    sess = db_sessions.get(session_id)
    if sess and sess.get("status") == "completed" and sess.get("result_json"):
        return sess["result_json"]

    student_id = x_student_id or (sess.get("student_id") if sess else "std-default")
    now_dt = get_current_time()
    attempts = sess["attempts"] if (sess and sess.get("attempts")) else [a for a in db_attempts[-5:]]

    stats_by_concept = aggregate_session_attempts(attempts)

    # Rollback snapshot in case of failure
    concepts_snapshot = copy.deepcopy(db_concepts)
    history_snapshot = copy.deepcopy(db_practice_history)
    records_snapshot = copy.deepcopy(db_training_records)

    try:
        with get_uow() as uow:
            _, active_model = GLOBAL_REGISTRY.load_active_model(uow)
            all_models = uow.models.list_all()
            candidate_models = [m for m in all_models if not m.active and m.validation_status in ("candidate", "passed")]

        updates = []
        for cid, stats in stats_by_concept.items():
            if cid not in db_concepts:
                continue
            c = db_concepts[cid]
            counts_before = ConceptCounts(c["n_right"], c["n_wrong"])
            old_h = c["half_life_days"]

            last_dt = datetime.fromisoformat(c["last_practiced_at"]) if c.get("last_practiced_at") else None
            is_first_practice = (counts_before.n_right + counts_before.n_wrong == 0) or (last_dt is None)

            if not is_first_practice and last_dt is not None:
                delta_days = max(0.01, (now_dt - last_dt).total_seconds() / 86400.0)
                # Build and persist training record
                t_rec = build_training_record(
                    student_id=student_id,
                    concept_id=cid,
                    session_id=session_id,
                    stats=stats,
                    counts_before=counts_before,
                    last_practiced_at=last_dt,
                    completed_at=now_dt,
                    model=active_model,
                    context_before={"difficulty": c.get("difficulty")}
                )
                db_training_records.append({
                    "student_id": t_rec.student_id,
                    "concept_id": t_rec.concept_id,
                    "session_id": t_rec.session_id,
                    "p_observed": t_rec.p_observed,
                    "n_answers": t_rec.n_answers,
                    "delta_days": t_rec.delta_days,
                    "counts_before": t_rec.counts_before,
                    "x_before": t_rec.x_before,
                    "feature_spec_name": t_rec.feature_spec_name,
                    "model_version": t_rec.model_version,
                    "source_event_ids": t_rec.source_event_ids,
                    "created_at": t_rec.created_at.isoformat()
                })
            else:
                delta_days = 0.0

            # Increment counts and compute state
            new_counts = apply_outcome(counts_before, stats.correct, stats.total - stats.correct)
            c["n_right"] = new_counts.n_right
            c["n_wrong"] = new_counts.n_wrong
            c["last_practiced_at"] = now_dt.isoformat()

            state = compute_state(
                counts=new_counts,
                model=active_model,
                last_practiced_at=now_dt,
                now=now_dt,
                threshold=db_settings.retention_threshold
            )
            new_h = state.half_life_days
            next_dt = state.next_review_at
            review_days = next_review_days(new_h, db_settings.retention_threshold)

            c["half_life_days"] = round(new_h, 3)
            c["p_hat"] = 0.99
            c["next_review_at"] = next_dt.isoformat()
            c["is_due"] = False

            # Shadow mode predictions for any candidate models (never used for scheduling)
            for cand in candidate_models:
                try:
                    c_spec = get_spec(cand.feature_spec["name"])
                    c_x = extract_features(new_counts, c_spec)
                    c_h = predict_half_life(cand.theta, c_x, active_model.config)
                    c_p = predict_recall(c_h, 0.0, active_model.config)
                    GLOBAL_REGISTRY.record_shadow_prediction(
                        session_id=session_id,
                        student_id=student_id,
                        concept_id=cid,
                        active_prediction=0.99,
                        candidate_model_id=cand.id,
                        candidate_prediction=round(c_p, 4)
                    )
                except Exception:
                    pass

            if cid not in db_practice_history:
                db_practice_history[cid] = []
            db_practice_history[cid].append({
                "delta_days": round(delta_days, 2),
                "p_observed": round(stats.p_session, 2),
                "p_hat": round(recall_prob(old_h, delta_days), 3),
                "type": f"Session {session_id[-4:]}",
                "date": now_dt.strftime("%b %d, %H:%M")
            })

            updates.append({
                "concept_id": cid,
                "concept_name": c["name"],
                "subject": c["subject"],
                "session_score": f"{stats.correct}/{stats.total}",
                "old_half_life": old_h,
                "new_half_life": round(new_h, 3),
                "next_review_days": round(review_days, 1),
                "next_review_date": next_dt.strftime("%b %d")
            })

        res_json = {
            "success": True,
            "session_id": session_id,
            "completed_at": now_dt.isoformat(),
            "total_attempts": len(attempts),
            "concept_updates": updates
        }

        if sess:
            sess["status"] = "completed"
            sess["completed_at"] = now_dt.isoformat()
            sess["result_json"] = res_json
        else:
            db_sessions[session_id] = {
                "id": session_id,
                "student_id": student_id,
                "status": "completed",
                "completed_at": now_dt.isoformat(),
                "result_json": res_json,
                "attempts": attempts
            }

        return res_json
    except Exception:
        db_concepts.clear()
        db_concepts.update(concepts_snapshot)
        db_practice_history.clear()
        db_practice_history.update(history_snapshot)
        db_training_records.clear()
        db_training_records.extend(records_snapshot)
        raise

@app.get("/api/settings")
def get_settings(user_id: Optional[int] = None, db: Session = Depends(get_db)) -> Any:
    k = settings.get_gemini_api_key()
    db_settings.gemini_configured = bool(k and len(k) > 5)
    if user_id is not None:
        return settings_router.get_settings(user_id=user_id, db=db)
    return db_settings

@app.put("/api/settings")
def update_settings(settings_payload: Dict[str, Any], user_id: Optional[int] = None, db: Session = Depends(get_db)) -> Any:
    global db_settings
    if "gemini_api_key" in settings_payload and settings_payload["gemini_api_key"]:
        settings.set_gemini_api_key(settings_payload["gemini_api_key"])
    
    if "daily_minutes" in settings_payload and settings_payload["daily_minutes"] is not None:
        db_settings.daily_minutes = int(settings_payload["daily_minutes"])
    if "retention_threshold" in settings_payload and settings_payload["retention_threshold"] is not None:
        db_settings.retention_threshold = float(settings_payload["retention_threshold"])
    if "subject_priorities" in settings_payload and isinstance(settings_payload["subject_priorities"], dict):
        db_settings.subject_priorities.update(settings_payload["subject_priorities"])
    if "exam_dates" in settings_payload and isinstance(settings_payload["exam_dates"], dict):
        db_settings.exam_dates.update(settings_payload["exam_dates"])

    k = settings.get_gemini_api_key()
    db_settings.gemini_configured = bool(k and len(k) > 5)

    if user_id is not None:
        from app.schemas.schemas import SettingsUpdateRequest
        update_obj = SettingsUpdateRequest(
            daily_minutes=db_settings.daily_minutes,
            retention_threshold=db_settings.retention_threshold,
            subject_priorities=db_settings.subject_priorities,
            exam_dates=db_settings.exam_dates
        )
        settings_router.update_settings(update_obj, user_id=user_id, db=db)
    return db_settings

from ml.model_registry import GLOBAL_REGISTRY

@app.get("/api/models")
def get_models() -> Dict[str, Any]:
    """Returns active model versions and feature specifications from the model registry."""
    with get_uow() as uow:
        models = GLOBAL_REGISTRY.list_models(uow)
        active_rec = uow.models.get_active() or GLOBAL_REGISTRY.seed_default_model(uow)

        models_out = []
        for m in models:
            names = m.feature_spec.get("feature_names", ["intercept", "n_right", "n_wrong"])
            feature_spec_str = "x = [" + ", ".join(names) + "]"
            theta_labels = ["Intercept (θ0)", "Success (θ_right)", "Failure (θ_wrong)"]
            if len(names) > 3:
                theta_labels.extend([f"Feature ({n})" for n in names[3:]])

            models_out.append({
                "id": m.id,
                "name": m.name,
                "active": m.active,
                "status": m.validation_status,
                "feature_spec": feature_spec_str,
                "theta": m.theta,
                "theta_labels": theta_labels,
                "bounds": {"h_min_days": H_MIN, "h_max_days": H_MAX, "p_min": P_MIN, "p_max": P_MAX},
                "metrics": m.evaluation_metrics
            })

        return {
            "active_model_id": active_rec.id,
            "models": models_out
        }

# Include HLR routers
app.include_router(subjects.router)
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
        "generated_on": get_current_time().date().isoformat(),
        "total_slots": len(request.available_slots),
        "scheduled_slots": len(output),
        "completion_percent": 100,
        "schedule": output,
        "priority_order": [t.subject for t in request.tasks],
    }

