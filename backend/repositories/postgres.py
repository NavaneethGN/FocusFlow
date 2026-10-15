"""
backend/repositories/postgres.py
SQLAlchemy 2.0 PostgreSQL repository implementation.
Enforces table schemas, CHECK constraints, and UnitOfWork transaction isolation.
"""
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    String,
    Boolean,
    Float,
    DateTime,
    JSON,
    CheckConstraint,
    UniqueConstraint,
    Index,
    select,
    update,
    event,
)
from sqlalchemy.orm import declarative_base, sessionmaker, Session

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

Base = declarative_base()

class AttemptModel(Base):
    __tablename__ = "attempts"
    id = Column(Integer, primary_key=True, autoincrement=True)
    event_id = Column(String(64), unique=True, nullable=False, index=True)
    student_id = Column(String(64), nullable=False, index=True)
    session_id = Column(String(64), nullable=False, index=True)
    question_id = Column(String(64), nullable=False)
    concept_id = Column(String(64), nullable=False, index=True)
    correct = Column(Boolean, nullable=False)
    answered_at = Column(DateTime(timezone=True), nullable=False)
    selected_option = Column(Integer, nullable=False)
    response_time_ms = Column(Integer, nullable=True)
    hint_used = Column(Boolean, default=False, nullable=False)

# Guard: attempts table is append-only
@event.listens_for(AttemptModel, "before_update")
def _prevent_attempt_update(mapper, connection, target):
    raise ImmutableRecordError("Attempts table is append-only; update is rejected")

@event.listens_for(AttemptModel, "before_delete")
def _prevent_attempt_delete(mapper, connection, target):
    raise ImmutableRecordError("Attempts table is append-only; delete is rejected")

class SessionModel(Base):
    __tablename__ = "sessions"
    id = Column(String(64), primary_key=True)
    student_id = Column(String(64), nullable=False, index=True)
    started_at = Column(DateTime(timezone=True), nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    status = Column(String(32), default="open", nullable=False)
    result_json = Column(JSON, nullable=True)

class ConceptStateModel(Base):
    __tablename__ = "concept_state"
    id = Column(Integer, primary_key=True, autoincrement=True)
    student_id = Column(String(64), nullable=False)
    concept_id = Column(String(64), nullable=False)
    n_right = Column(Integer, nullable=False)
    n_wrong = Column(Integer, nullable=False)
    last_practiced_at = Column(DateTime(timezone=True), nullable=False)
    half_life_days = Column(Float, nullable=False)
    recall_prob_now = Column(Float, nullable=False)
    next_review_at = Column(DateTime(timezone=True), nullable=False)
    model_version = Column(String(64), nullable=False)
    version = Column(Integer, default=1, nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        UniqueConstraint("student_id", "concept_id", name="uq_student_concept"),
        CheckConstraint("n_right >= 0", name="chk_n_right_non_negative"),
        CheckConstraint("n_wrong >= 0", name="chk_n_wrong_non_negative"),
    )

class PracticeHistoryModel(Base):
    __tablename__ = "practice_history"
    id = Column(Integer, primary_key=True, autoincrement=True)
    student_id = Column(String(64), nullable=False, index=True)
    concept_id = Column(String(64), nullable=False, index=True)
    delta_days = Column(Float, nullable=False)
    p_observed = Column(Float, nullable=False)
    p_hat = Column(Float, nullable=False)
    type = Column(String(64), nullable=False)
    date_str = Column(String(64), nullable=False)

class TrainingRecordModel(Base):
    __tablename__ = "training_records"
    id = Column(Integer, primary_key=True, autoincrement=True)
    student_id = Column(String(64), nullable=False, index=True)
    concept_id = Column(String(64), nullable=False)
    session_id = Column(String(64), nullable=False)
    p_observed = Column(Float, nullable=False)
    n_answers = Column(Integer, nullable=False)
    delta_days = Column(Float, nullable=False)
    counts_before = Column(JSON, nullable=False)
    x_before = Column(JSON, nullable=False)
    feature_spec_name = Column(String(64), nullable=False)
    label_definition_version = Column(String(32), default="1.0", nullable=False)
    model_version = Column(String(64), nullable=False)
    source_event_ids = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        UniqueConstraint("session_id", "concept_id", name="uq_session_concept"),
        CheckConstraint("p_observed >= 0.0 AND p_observed <= 1.0", name="chk_p_observed_bounds"),
        CheckConstraint("n_answers >= 1", name="chk_n_answers_positive"),
    )

class ModelVersionModel(Base):
    __tablename__ = "model_versions"
    id = Column(String(64), primary_key=True)
    name = Column(String(64), nullable=False)
    version = Column(String(32), nullable=False)
    theta = Column(JSON, nullable=False)
    feature_spec = Column(JSON, nullable=False)
    training_config = Column(JSON, nullable=False)
    dataset_snapshot_id = Column(String(64), nullable=True)
    evaluation_metrics = Column(JSON, nullable=True)
    validation_status = Column(String(32), default="candidate", nullable=False)
    active = Column(Boolean, default=False, nullable=False)
    checksum = Column(String(128), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        Index("uq_active_model", "active", unique=True, postgresql_where=(active == True)),
    )

class PostgresAttemptRepo(AttemptRepo):
    def __init__(self, session: Session):
        self.session = session

    def add(self, attempt: AttemptRecord) -> AttemptRecord:
        existing = self.session.execute(
            select(AttemptModel).where(AttemptModel.event_id == attempt.event_id)
        ).scalar_one_or_none()
        if existing:
            raise DuplicateKeyError(f"Attempt event_id '{attempt.event_id}' already exists")
        m = AttemptModel(
            event_id=attempt.event_id,
            student_id=attempt.student_id,
            session_id=attempt.session_id,
            question_id=attempt.question_id,
            concept_id=attempt.concept_id,
            correct=attempt.correct,
            answered_at=attempt.answered_at,
            selected_option=attempt.selected_option,
            response_time_ms=attempt.response_time_ms,
            hint_used=attempt.hint_used
        )
        self.session.add(m)
        self.session.flush()
        attempt.id = m.id
        return attempt

    def get_by_event_id(self, event_id: str) -> Optional[AttemptRecord]:
        m = self.session.execute(
            select(AttemptModel).where(AttemptModel.event_id == event_id)
        ).scalar_one_or_none()
        if not m:
            return None
        return AttemptRecord(
            id=m.id,
            event_id=m.event_id,
            student_id=m.student_id,
            session_id=m.session_id,
            question_id=m.question_id,
            concept_id=m.concept_id,
            correct=m.correct,
            answered_at=m.answered_at,
            selected_option=m.selected_option,
            response_time_ms=m.response_time_ms,
            hint_used=m.hint_used
        )

    def list_by_session(self, session_id: str) -> List[AttemptRecord]:
        rows = self.session.execute(
            select(AttemptModel).where(AttemptModel.session_id == session_id)
        ).scalars().all()
        return [
            AttemptRecord(
                id=m.id,
                event_id=m.event_id,
                student_id=m.student_id,
                session_id=m.session_id,
                question_id=m.question_id,
                concept_id=m.concept_id,
                correct=m.correct,
                answered_at=m.answered_at,
                selected_option=m.selected_option,
                response_time_ms=m.response_time_ms,
                hint_used=m.hint_used
            )
            for m in rows
        ]

class PostgresSessionRepo(SessionRepo):
    def __init__(self, session: Session):
        self.session = session

    def create(self, s: SessionRecord) -> SessionRecord:
        existing = self.session.get(SessionModel, s.id)
        if existing:
            raise DuplicateKeyError(f"Session '{s.id}' already exists")
        m = SessionModel(
            id=s.id,
            student_id=s.student_id,
            started_at=s.started_at,
            completed_at=s.completed_at,
            status=s.status,
            result_json=s.result_json
        )
        self.session.add(m)
        self.session.flush()
        return s

    def get(self, session_id: str) -> Optional[SessionRecord]:
        m = self.session.get(SessionModel, session_id)
        if not m:
            return None
        return SessionRecord(
            id=m.id,
            student_id=m.student_id,
            started_at=m.started_at,
            completed_at=m.completed_at,
            status=m.status,
            result_json=m.result_json
        )

    def update(self, s: SessionRecord) -> SessionRecord:
        m = self.session.get(SessionModel, s.id)
        if not m:
            raise KeyError(f"Session '{s.id}' not found")
        m.status = s.status
        m.completed_at = s.completed_at
        m.result_json = s.result_json
        self.session.flush()
        return s

class PostgresConceptStateRepo(ConceptStateRepo):
    def __init__(self, session: Session):
        self.session = session

    def get(self, student_id: str, concept_id: str) -> Optional[ConceptStateRecord]:
        m = self.session.execute(
            select(ConceptStateModel).where(
                ConceptStateModel.student_id == student_id,
                ConceptStateModel.concept_id == concept_id
            )
        ).scalar_one_or_none()
        if not m:
            return None
        return ConceptStateRecord(
            id=m.id,
            student_id=m.student_id,
            concept_id=m.concept_id,
            n_right=m.n_right,
            n_wrong=m.n_wrong,
            last_practiced_at=m.last_practiced_at,
            half_life_days=m.half_life_days,
            recall_prob_now=m.recall_prob_now,
            next_review_at=m.next_review_at,
            model_version=m.model_version,
            version=m.version,
            updated_at=m.updated_at
        )

    def upsert(self, state: ConceptStateRecord) -> ConceptStateRecord:
        if state.n_right < 0 or state.n_wrong < 0:
            raise ConstraintViolationError("n_right and n_wrong must be non-negative")
        m = self.session.execute(
            select(ConceptStateModel).where(
                ConceptStateModel.student_id == state.student_id,
                ConceptStateModel.concept_id == state.concept_id
            )
        ).scalar_one_or_none()
        if m:
            if state.version != m.version:
                raise ConcurrencyError(
                    f"Optimistic lock failure: expected version {m.version}, got {state.version}"
                )
            m.n_right = state.n_right
            m.n_wrong = state.n_wrong
            m.last_practiced_at = state.last_practiced_at
            m.half_life_days = state.half_life_days
            m.recall_prob_now = state.recall_prob_now
            m.next_review_at = state.next_review_at
            m.model_version = state.model_version
            m.updated_at = state.updated_at
            m.version += 1
            self.session.flush()
            state.version = m.version
            state.id = m.id
        else:
            m = ConceptStateModel(
                student_id=state.student_id,
                concept_id=state.concept_id,
                n_right=state.n_right,
                n_wrong=state.n_wrong,
                last_practiced_at=state.last_practiced_at,
                half_life_days=state.half_life_days,
                recall_prob_now=state.recall_prob_now,
                next_review_at=state.next_review_at,
                model_version=state.model_version,
                version=1,
                updated_at=state.updated_at
            )
            self.session.add(m)
            self.session.flush()
            state.id = m.id
            state.version = 1
        return state

    def list_by_student(self, student_id: str) -> List[ConceptStateRecord]:
        rows = self.session.execute(
            select(ConceptStateModel).where(ConceptStateModel.student_id == student_id)
        ).scalars().all()
        return [
            ConceptStateRecord(
                id=m.id,
                student_id=m.student_id,
                concept_id=m.concept_id,
                n_right=m.n_right,
                n_wrong=m.n_wrong,
                last_practiced_at=m.last_practiced_at,
                half_life_days=m.half_life_days,
                recall_prob_now=m.recall_prob_now,
                next_review_at=m.next_review_at,
                model_version=m.model_version,
                version=m.version,
                updated_at=m.updated_at
            )
            for m in rows
        ]

class PostgresPracticeHistoryRepo(PracticeHistoryRepo):
    def __init__(self, session: Session):
        self.session = session

    def add(self, p: PracticeHistoryRecord) -> PracticeHistoryRecord:
        m = PracticeHistoryModel(
            student_id=p.student_id,
            concept_id=p.concept_id,
            delta_days=p.delta_days,
            p_observed=p.p_observed,
            p_hat=p.p_hat,
            type=p.type,
            date_str=p.date_str
        )
        self.session.add(m)
        self.session.flush()
        p.id = m.id
        return p

    def list_by_concept(self, student_id: str, concept_id: str) -> List[PracticeHistoryRecord]:
        rows = self.session.execute(
            select(PracticeHistoryModel).where(
                PracticeHistoryModel.student_id == student_id,
                PracticeHistoryModel.concept_id == concept_id
            )
        ).scalars().all()
        return [
            PracticeHistoryRecord(
                id=m.id,
                student_id=m.student_id,
                concept_id=m.concept_id,
                delta_days=m.delta_days,
                p_observed=m.p_observed,
                p_hat=m.p_hat,
                type=m.type,
                date_str=m.date_str
            )
            for m in rows
        ]

class PostgresTrainingRecordRepo(TrainingRecordRepo):
    def __init__(self, session: Session):
        self.session = session

    def add(self, r: TrainingRecord) -> TrainingRecord:
        if not (0.0 <= r.p_observed <= 1.0):
            raise ConstraintViolationError(f"p_observed must be in [0, 1], got {r.p_observed}")
        if r.n_answers < 1:
            raise ConstraintViolationError(f"n_answers must be >= 1, got {r.n_answers}")

        existing = self.session.execute(
            select(TrainingRecordModel).where(
                TrainingRecordModel.session_id == r.session_id,
                TrainingRecordModel.concept_id == r.concept_id
            )
        ).scalar_one_or_none()
        if existing:
            raise DuplicateKeyError(f"Training record for session {r.session_id} concept {r.concept_id} already exists")

        m = TrainingRecordModel(
            student_id=r.student_id,
            concept_id=r.concept_id,
            session_id=r.session_id,
            p_observed=r.p_observed,
            n_answers=r.n_answers,
            delta_days=r.delta_days,
            counts_before=r.counts_before,
            x_before=r.x_before,
            feature_spec_name=r.feature_spec_name,
            label_definition_version=r.label_definition_version,
            model_version=r.model_version,
            source_event_ids=r.source_event_ids,
            created_at=r.created_at
        )
        self.session.add(m)
        self.session.flush()
        r.id = m.id
        return r

    def list_all(self) -> List[TrainingRecord]:
        rows = self.session.execute(select(TrainingRecordModel)).scalars().all()
        return [
            TrainingRecord(
                id=m.id,
                student_id=m.student_id,
                concept_id=m.concept_id,
                session_id=m.session_id,
                p_observed=m.p_observed,
                n_answers=m.n_answers,
                delta_days=m.delta_days,
                counts_before=m.counts_before,
                x_before=m.x_before,
                feature_spec_name=m.feature_spec_name,
                label_definition_version=m.label_definition_version,
                model_version=m.model_version,
                source_event_ids=m.source_event_ids,
                created_at=m.created_at
            )
            for m in rows
        ]

class PostgresModelRepo(ModelRepo):
    def __init__(self, session: Session):
        self.session = session

    def register(self, m: ModelVersionRecord) -> ModelVersionRecord:
        m_id = m.id or f"m-{m.name}-{m.version}"
        existing = self.session.get(ModelVersionModel, m_id)
        if existing:
            raise DuplicateKeyError(f"Model version '{m_id}' already registered")
        if m.active:
            # Enforce at most one active model
            self.session.execute(
                update(ModelVersionModel).values(active=False)
            )
        rec = ModelVersionModel(
            id=m_id,
            name=m.name,
            version=m.version,
            theta=m.theta,
            feature_spec=m.feature_spec,
            training_config=m.training_config,
            dataset_snapshot_id=m.dataset_snapshot_id,
            evaluation_metrics=m.evaluation_metrics,
            validation_status=m.validation_status,
            active=m.active,
            checksum=m.checksum,
            created_at=m.created_at or datetime.now(timezone.utc)
        )
        self.session.add(rec)
        self.session.flush()
        m.id = m_id
        return m

    def get(self, model_id: str) -> Optional[ModelVersionRecord]:
        rec = self.session.get(ModelVersionModel, model_id)
        if not rec:
            return None
        return ModelVersionRecord(
            id=rec.id,
            name=rec.name,
            version=rec.version,
            theta=rec.theta,
            feature_spec=rec.feature_spec,
            training_config=rec.training_config,
            dataset_snapshot_id=rec.dataset_snapshot_id,
            evaluation_metrics=rec.evaluation_metrics,
            validation_status=rec.validation_status,
            active=rec.active,
            checksum=rec.checksum,
            created_at=rec.created_at
        )

    def get_active(self) -> Optional[ModelVersionRecord]:
        rec = self.session.execute(
            select(ModelVersionModel).where(ModelVersionModel.active == True)
        ).scalar_one_or_none()
        if not rec:
            return None
        return ModelVersionRecord(
            id=rec.id,
            name=rec.name,
            version=rec.version,
            theta=rec.theta,
            feature_spec=rec.feature_spec,
            training_config=rec.training_config,
            dataset_snapshot_id=rec.dataset_snapshot_id,
            evaluation_metrics=rec.evaluation_metrics,
            validation_status=rec.validation_status,
            active=rec.active,
            checksum=rec.checksum,
            created_at=rec.created_at
        )

    def set_active(self, model_id: str) -> ModelVersionRecord:
        target = self.session.get(ModelVersionModel, model_id)
        if not target:
            raise KeyError(f"Model '{model_id}' does not exist")
        self.session.execute(update(ModelVersionModel).values(active=False))
        target.active = True
        self.session.flush()
        return self.get(model_id)

    def list_all(self) -> List[ModelVersionRecord]:
        rows = self.session.execute(select(ModelVersionModel)).scalars().all()
        return [
            ModelVersionRecord(
                id=rec.id,
                name=rec.name,
                version=rec.version,
                theta=rec.theta,
                feature_spec=rec.feature_spec,
                training_config=rec.training_config,
                dataset_snapshot_id=rec.dataset_snapshot_id,
                evaluation_metrics=rec.evaluation_metrics,
                validation_status=rec.validation_status,
                active=rec.active,
                checksum=rec.checksum,
                created_at=rec.created_at
            )
            for rec in rows
        ]

class PostgresUnitOfWork(UnitOfWork):
    def __init__(self, session_factory):
        self.session_factory = session_factory
        self.session: Optional[Session] = None

    def __enter__(self) -> "PostgresUnitOfWork":
        self.session = self.session_factory()
        self.attempts = PostgresAttemptRepo(self.session)
        self.sessions = PostgresSessionRepo(self.session)
        self.concept_states = PostgresConceptStateRepo(self.session)
        self.practice_history = PostgresPracticeHistoryRepo(self.session)
        self.training_records = PostgresTrainingRecordRepo(self.session)
        self.models = PostgresModelRepo(self.session)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.session is not None:
            if exc_type is not None:
                self.rollback()
            else:
                self.commit()
            self.session.close()

    def commit(self) -> None:
        if self.session is not None:
            self.session.commit()

    def rollback(self) -> None:
        if self.session is not None:
            self.session.rollback()
