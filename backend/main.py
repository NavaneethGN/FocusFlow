import math
import copy
import uuid
from datetime import datetime, timezone, timedelta
from typing import Literal, Optional, List, Dict, Any
from fastapi import FastAPI, HTTPException, Query, Header, Depends
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
    concept_id: str
    question_id: str
    is_correct: bool = True
    selected_index: int
    response_time_ms: int = 1500
    answered_at: Optional[str] = None

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
        "Artificial Intelligence": (get_current_time() + timedelta(days=14)).strftime("%Y-%m-%d"),
        "Operating Systems": (get_current_time() + timedelta(days=21)).strftime("%Y-%m-%d"),
        "Mathematics": (get_current_time() + timedelta(days=30)).strftime("%Y-%m-%d"),
        "Distributed Systems": (get_current_time() + timedelta(days=28)).strftime("%Y-%m-%d"),
    }

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

# Database state
db_concepts: Dict[str, Dict[str, Any]] = {}
db_questions: List[Dict[str, Any]] = [q.copy() for q in INITIAL_QUESTIONS]
db_attempts: List[Dict[str, Any]] = []
db_sessions: Dict[str, Dict[str, Any]] = {}
db_settings = UserSettings()
db_training_records: List[Dict[str, Any]] = []

# Practice history records for forgetting curves (simulated past review checkpoints)
db_practice_history: Dict[str, List[Dict[str, Any]]] = {}

def init_db():
    global NOW, db_concepts, db_questions, db_attempts, db_sessions, db_practice_history, db_settings, db_training_records
    NOW = get_current_time()
    db_concepts.clear()
    db_questions.clear()
    db_questions.extend([q.copy() for q in INITIAL_QUESTIONS])
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
# FastAPI App & Middleware
# ---------------------------------------------------------------------------
app = FastAPI(
    title="FocusFlow HLR Study Planner API",
    description="Adaptive spaced repetition engine based on Half-Life Regression (Settles & Meeder, 2016)",
    version="2.0.0",
)

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
# API Endpoints
# ---------------------------------------------------------------------------

@app.get("/api/health")
def health() -> Dict[str, Any]:
    return {
        "status": "healthy",
        "engine": "Half-Life Regression (HLR)",
        "concepts_count": len(db_concepts),
        "questions_count": len(db_questions),
        "timestamp": get_current_time().isoformat()
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
        "last_practiced_at": get_current_time().isoformat(),
        "half_life_days": 1.0,
        "p_hat": 0.99,
        "next_review_at": (get_current_time() + timedelta(days=1)).isoformat(),
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
        delta = max(0.0, (get_current_time() - last_dt).total_seconds() / 86400.0)
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
        "date": get_current_time().strftime("%Y-%m-%d"),
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
    today = get_current_time()
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
    student_id: str = Depends(get_current_student)
) -> Dict[str, Any]:
    """Records an answered question event idempotently, validating session and server-scoring."""
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
    x_student_id: Optional[str] = Header(None, alias="X-Student-Id")
) -> Dict[str, Any]:
    """
    Session completion pipeline:
    1. Lock session. If already completed, return stored result_json idempotently.
    2. Group scored attempts by concept using session_aggregator.
    3. If practiced before, build and persist training_record holding p_session.
    4. Apply outcomes, compute new state with active model, update concept state and practice history.
    5. Mark session completed and return result_json. Rollback on failure.
    """
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
def get_settings() -> UserSettings:
    return db_settings

@app.put("/api/settings")
def update_settings(settings: UserSettings) -> UserSettings:
    global db_settings
    db_settings = settings
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
        "generated_on": get_current_time().strftime("%Y-%m-%d"),
        "total_slots": len(request.available_slots),
        "scheduled_slots": len(output),
        "completion_percent": 100,
        "schedule": output,
        "priority_order": [t.subject for t in request.tasks]
    }
