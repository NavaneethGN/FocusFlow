"""
backend/repositories/base.py
Abstract repository interfaces and UnitOfWork contract.
Pure abstraction layer separating domain logic from storage mechanisms.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List, Dict, Any

class RepositoryError(Exception):
    """Base exception for repository errors."""
    pass

class DuplicateKeyError(RepositoryError):
    """Raised when a unique constraint or primary key is violated."""
    pass

class ConstraintViolationError(RepositoryError):
    """Raised when a domain check constraint is violated."""
    pass

class ConcurrencyError(RepositoryError):
    """Raised on optimistic locking conflict."""
    pass

class ImmutableRecordError(RepositoryError):
    """Raised when an append-only table is subjected to an update or delete."""
    pass

# Domain entities
@dataclass
class AttemptRecord:
    event_id: str
    student_id: str
    session_id: str
    question_id: str
    concept_id: str
    correct: bool
    answered_at: datetime
    selected_option: int
    response_time_ms: Optional[int] = None
    hint_used: bool = False
    id: Optional[int] = None

@dataclass
class SessionRecord:
    id: str
    student_id: str
    started_at: datetime
    status: str = "open"  # 'open', 'processing', 'completed', 'cancelled'
    completed_at: Optional[datetime] = None
    result_json: Optional[Dict[str, Any]] = None

@dataclass
class ConceptStateRecord:
    student_id: str
    concept_id: str
    n_right: int
    n_wrong: int
    last_practiced_at: datetime
    half_life_days: float
    recall_prob_now: float
    next_review_at: datetime
    model_version: str
    updated_at: datetime
    version: int = 1
    id: Optional[int] = None

@dataclass
class PracticeHistoryRecord:
    student_id: str
    concept_id: str
    delta_days: float
    p_observed: float
    p_hat: float
    type: str
    date_str: str
    id: Optional[int] = None

@dataclass
class TrainingRecord:
    student_id: str
    concept_id: str
    session_id: str
    p_observed: float
    n_answers: int
    delta_days: float
    counts_before: Dict[str, Any]
    x_before: List[float]
    feature_spec_name: str
    model_version: str
    source_event_ids: List[str]
    created_at: datetime
    label_definition_version: str = "1.0"
    id: Optional[int] = None

@dataclass
class ModelVersionRecord:
    name: str
    version: str
    theta: List[float]
    feature_spec: Dict[str, Any]
    training_config: Dict[str, Any]
    checksum: str
    id: Optional[str] = None
    dataset_snapshot_id: Optional[str] = None
    evaluation_metrics: Optional[Dict[str, Any]] = None
    validation_status: str = "candidate"  # 'candidate', 'passed', 'failed', 'active', 'provisional_fixed_weights'
    active: bool = False
    created_at: Optional[datetime] = None

class AttemptRepo(ABC):
    @abstractmethod
    def add(self, attempt: AttemptRecord) -> AttemptRecord:
        """Append an attempt. Must be idempotent on event_id. Rejects updates and deletes."""
        pass

    @abstractmethod
    def get_by_event_id(self, event_id: str) -> Optional[AttemptRecord]:
        pass

    @abstractmethod
    def list_by_session(self, session_id: str) -> List[AttemptRecord]:
        pass

class SessionRepo(ABC):
    @abstractmethod
    def create(self, session: SessionRecord) -> SessionRecord:
        pass

    @abstractmethod
    def get(self, session_id: str) -> Optional[SessionRecord]:
        pass

    @abstractmethod
    def update(self, session: SessionRecord) -> SessionRecord:
        pass

class ConceptStateRepo(ABC):
    @abstractmethod
    def get(self, student_id: str, concept_id: str) -> Optional[ConceptStateRecord]:
        pass

    @abstractmethod
    def upsert(self, state: ConceptStateRecord) -> ConceptStateRecord:
        pass

    @abstractmethod
    def list_by_student(self, student_id: str) -> List[ConceptStateRecord]:
        pass

class PracticeHistoryRepo(ABC):
    @abstractmethod
    def add(self, record: PracticeHistoryRecord) -> PracticeHistoryRecord:
        pass

    @abstractmethod
    def list_by_concept(self, student_id: str, concept_id: str) -> List[PracticeHistoryRecord]:
        pass

class TrainingRecordRepo(ABC):
    @abstractmethod
    def add(self, record: TrainingRecord) -> TrainingRecord:
        pass

    @abstractmethod
    def list_all(self) -> List[TrainingRecord]:
        pass

class ModelRepo(ABC):
    @abstractmethod
    def register(self, model: ModelVersionRecord) -> ModelVersionRecord:
        pass

    @abstractmethod
    def get(self, model_id: str) -> Optional[ModelVersionRecord]:
        pass

    @abstractmethod
    def get_active(self) -> Optional[ModelVersionRecord]:
        pass

    @abstractmethod
    def set_active(self, model_id: str) -> ModelVersionRecord:
        """Atomically set model active and deactivate all others."""
        pass

    @abstractmethod
    def list_all(self) -> List[ModelVersionRecord]:
        pass

class UnitOfWork(ABC):
    attempts: AttemptRepo
    sessions: SessionRepo
    concept_states: ConceptStateRepo
    practice_history: PracticeHistoryRepo
    training_records: TrainingRecordRepo
    models: ModelRepo

    @abstractmethod
    def __enter__(self) -> "UnitOfWork":
        pass

    @abstractmethod
    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    @abstractmethod
    def commit(self) -> None:
        pass

    @abstractmethod
    def rollback(self) -> None:
        pass
