"""
backend/repositories/memory.py
Thread-safe In-Memory repository implementation of UnitOfWork and repository interfaces.
Enforces domain constraints, unique keys, and transactional atomicity.
"""
import copy
from typing import Optional, List, Dict, Any

from .base import (
    AttemptRecord,
    SessionRecord,
    ConceptStateRecord,
    PracticeHistoryRecord,
    TrainingRecord,
    ModelVersionRecord,
    AttemptRepo,
    SessionRepo,
    ConceptStateRepo,
    PracticeHistoryRepo,
    TrainingRecordRepo,
    ModelRepo,
    UnitOfWork,
    DuplicateKeyError,
    ConstraintViolationError,
    ConcurrencyError,
    ImmutableRecordError,
)

class InMemoryAttemptRepo(AttemptRepo):
    def __init__(self, storage: Dict[str, Any]):
        self._storage = storage

    def add(self, attempt: AttemptRecord) -> AttemptRecord:
        if attempt.event_id in self._storage["attempts_by_event"]:
            raise DuplicateKeyError(f"Attempt with event_id '{attempt.event_id}' already exists")
        rec = copy.deepcopy(attempt)
        rec.id = len(self._storage["attempts"]) + 1
        self._storage["attempts"].append(rec)
        self._storage["attempts_by_event"][rec.event_id] = rec
        return copy.deepcopy(rec)

    def get_by_event_id(self, event_id: str) -> Optional[AttemptRecord]:
        rec = self._storage["attempts_by_event"].get(event_id)
        return copy.deepcopy(rec) if rec else None

    def list_by_session(self, session_id: str) -> List[AttemptRecord]:
        return [
            copy.deepcopy(a) for a in self._storage["attempts"]
            if a.session_id == session_id
        ]

    def update(self, *args, **kwargs):
        raise ImmutableRecordError("Attempts table is append-only; update is rejected")

    def delete(self, *args, **kwargs):
        raise ImmutableRecordError("Attempts table is append-only; delete is rejected")

class InMemorySessionRepo(SessionRepo):
    def __init__(self, storage: Dict[str, Any]):
        self._storage = storage

    def create(self, session: SessionRecord) -> SessionRecord:
        if session.id in self._storage["sessions"]:
            raise DuplicateKeyError(f"Session with id '{session.id}' already exists")
        rec = copy.deepcopy(session)
        self._storage["sessions"][session.id] = rec
        return copy.deepcopy(rec)

    def get(self, session_id: str) -> Optional[SessionRecord]:
        rec = self._storage["sessions"].get(session_id)
        return copy.deepcopy(rec) if rec else None

    def update(self, session: SessionRecord) -> SessionRecord:
        if session.id not in self._storage["sessions"]:
            raise KeyError(f"Session '{session.id}' not found")
        self._storage["sessions"][session.id] = copy.deepcopy(session)
        return copy.deepcopy(session)

class InMemoryConceptStateRepo(ConceptStateRepo):
    def __init__(self, storage: Dict[str, Any]):
        self._storage = storage

    def get(self, student_id: str, concept_id: str) -> Optional[ConceptStateRecord]:
        key = (student_id, concept_id)
        rec = self._storage["concept_states"].get(key)
        return copy.deepcopy(rec) if rec else None

    def upsert(self, state: ConceptStateRecord) -> ConceptStateRecord:
        if state.n_right < 0 or state.n_wrong < 0:
            raise ConstraintViolationError("n_right and n_wrong must be >= 0")
        key = (state.student_id, state.concept_id)
        existing = self._storage["concept_states"].get(key)
        rec = copy.deepcopy(state)
        if existing:
            if rec.version != existing.version:
                raise ConcurrencyError(
                    f"Optimistic lock failure for concept {key}: expected version {existing.version}, got {rec.version}"
                )
            rec.version += 1
            rec.id = existing.id
        else:
            rec.id = len(self._storage["concept_states"]) + 1
            rec.version = 1
        self._storage["concept_states"][key] = rec
        return copy.deepcopy(rec)

    def list_by_student(self, student_id: str) -> List[ConceptStateRecord]:
        return [
            copy.deepcopy(rec) for (s_id, _), rec in self._storage["concept_states"].items()
            if s_id == student_id
        ]

class InMemoryPracticeHistoryRepo(PracticeHistoryRepo):
    def __init__(self, storage: Dict[str, Any]):
        self._storage = storage

    def add(self, record: PracticeHistoryRecord) -> PracticeHistoryRecord:
        rec = copy.deepcopy(record)
        rec.id = len(self._storage["practice_history"]) + 1
        self._storage["practice_history"].append(rec)
        return copy.deepcopy(rec)

    def list_by_concept(self, student_id: str, concept_id: str) -> List[PracticeHistoryRecord]:
        return [
            copy.deepcopy(p) for p in self._storage["practice_history"]
            if p.student_id == student_id and p.concept_id == concept_id
        ]

class InMemoryTrainingRecordRepo(TrainingRecordRepo):
    def __init__(self, storage: Dict[str, Any]):
        self._storage = storage

    def add(self, record: TrainingRecord) -> TrainingRecord:
        if not (0.0 <= record.p_observed <= 1.0):
            raise ConstraintViolationError(f"p_observed must be between 0 and 1, got {record.p_observed}")
        if record.n_answers < 1:
            raise ConstraintViolationError(f"n_answers must be >= 1, got {record.n_answers}")

        key = (record.session_id, record.concept_id)
        if key in self._storage["training_records_by_session_concept"]:
            raise DuplicateKeyError(f"Training record for session {record.session_id} and concept {record.concept_id} already exists")

        rec = copy.deepcopy(record)
        rec.id = len(self._storage["training_records"]) + 1
        self._storage["training_records"].append(rec)
        self._storage["training_records_by_session_concept"][key] = rec
        return copy.deepcopy(rec)

    def list_all(self) -> List[TrainingRecord]:
        return [copy.deepcopy(r) for r in self._storage["training_records"]]

class InMemoryModelRepo(ModelRepo):
    def __init__(self, storage: Dict[str, Any]):
        self._storage = storage

    def register(self, model: ModelVersionRecord) -> ModelVersionRecord:
        m_id = model.id or f"m-{len(self._storage['models']) + 1}"
        if m_id in self._storage["models"]:
            raise DuplicateKeyError(f"Model '{m_id}' already registered")
        rec = copy.deepcopy(model)
        rec.id = m_id
        if rec.active:
            # Enforce at most one active model
            for m in self._storage["models"].values():
                m.active = False
        self._storage["models"][m_id] = rec
        return copy.deepcopy(rec)

    def get(self, model_id: str) -> Optional[ModelVersionRecord]:
        rec = self._storage["models"].get(model_id)
        return copy.deepcopy(rec) if rec else None

    def get_active(self) -> Optional[ModelVersionRecord]:
        for m in self._storage["models"].values():
            if m.active:
                return copy.deepcopy(m)
        return None

    def set_active(self, model_id: str) -> ModelVersionRecord:
        if model_id not in self._storage["models"]:
            raise KeyError(f"Model '{model_id}' does not exist")
        for m in self._storage["models"].values():
            m.active = (m.id == model_id)
        return copy.deepcopy(self._storage["models"][model_id])

    def list_all(self) -> List[ModelVersionRecord]:
        return [copy.deepcopy(m) for m in self._storage["models"].values()]

class InMemoryUnitOfWork(UnitOfWork):
    def __init__(self, master_storage: Optional[Dict[str, Any]] = None):
        if master_storage is None:
            self.master_storage = {
                "attempts": [],
                "attempts_by_event": {},
                "sessions": {},
                "concept_states": {},
                "practice_history": [],
                "training_records": [],
                "training_records_by_session_concept": {},
                "models": {}
            }
        else:
            self.master_storage = master_storage
        self.working_storage = None
        self.attempts = InMemoryAttemptRepo(self.master_storage)
        self.sessions = InMemorySessionRepo(self.master_storage)
        self.concept_states = InMemoryConceptStateRepo(self.master_storage)
        self.practice_history = InMemoryPracticeHistoryRepo(self.master_storage)
        self.training_records = InMemoryTrainingRecordRepo(self.master_storage)
        self.models = InMemoryModelRepo(self.master_storage)

    def __enter__(self) -> "InMemoryUnitOfWork":
        self.working_storage = copy.deepcopy(self.master_storage)
        self.attempts = InMemoryAttemptRepo(self.working_storage)
        self.sessions = InMemorySessionRepo(self.working_storage)
        self.concept_states = InMemoryConceptStateRepo(self.working_storage)
        self.practice_history = InMemoryPracticeHistoryRepo(self.working_storage)
        self.training_records = InMemoryTrainingRecordRepo(self.working_storage)
        self.models = InMemoryModelRepo(self.working_storage)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            self.rollback()
        else:
            self.commit()

    def commit(self) -> None:
        if self.working_storage is not None:
            # Overwrite master with committed working copy
            self.master_storage.clear()
            self.master_storage.update(self.working_storage)
            self.working_storage = None
            self.attempts = InMemoryAttemptRepo(self.master_storage)
            self.sessions = InMemorySessionRepo(self.master_storage)
            self.concept_states = InMemoryConceptStateRepo(self.master_storage)
            self.practice_history = InMemoryPracticeHistoryRepo(self.master_storage)
            self.training_records = InMemoryTrainingRecordRepo(self.master_storage)
            self.models = InMemoryModelRepo(self.master_storage)

    def rollback(self) -> None:
        self.working_storage = copy.deepcopy(self.master_storage)
