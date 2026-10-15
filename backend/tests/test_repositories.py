"""
tests/test_repositories.py
Single contract test suite testing both InMemory and Postgres/SQL UnitOfWork implementations.
"""
from datetime import datetime, timezone
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from repositories.base import (
    AttemptRecord,
    SessionRecord,
    ConceptStateRecord,
    PracticeHistoryRecord,
    TrainingRecord,
    ModelVersionRecord,
    DuplicateKeyError,
    ConstraintViolationError,
    ConcurrencyError,
    ImmutableRecordError,
)
from repositories.memory import InMemoryUnitOfWork
from repositories.postgres import PostgresUnitOfWork, Base

def create_memory_uow():
    return InMemoryUnitOfWork()

def create_sql_uow():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    return PostgresUnitOfWork(session_factory)

@pytest.fixture(params=["memory", "sql"])
def uow(request):
    if request.param == "memory":
        return create_memory_uow()
    else:
        return create_sql_uow()

NOW = datetime(2026, 10, 15, 12, 0, 0, tzinfo=timezone.utc)

def test_attempt_duplicate_event_id(uow):
    att1 = AttemptRecord(
        event_id="evt-100",
        student_id="std-1",
        session_id="sess-1",
        question_id="q-1",
        concept_id="c-1",
        correct=True,
        answered_at=NOW,
        selected_option=0
    )
    att2 = AttemptRecord(
        event_id="evt-100",
        student_id="std-2",
        session_id="sess-2",
        question_id="q-2",
        concept_id="c-2",
        correct=False,
        answered_at=NOW,
        selected_option=1
    )

    with uow:
        uow.attempts.add(att1)

    with pytest.raises(DuplicateKeyError):
        with uow:
            uow.attempts.add(att2)

def test_attempt_immutable(uow):
    att = AttemptRecord(
        event_id="evt-200",
        student_id="std-1",
        session_id="sess-1",
        question_id="q-1",
        concept_id="c-1",
        correct=True,
        answered_at=NOW,
        selected_option=0
    )
    with uow:
        uow.attempts.add(att)

    if hasattr(uow.attempts, "update"):
        with pytest.raises(ImmutableRecordError):
            uow.attempts.update()

    if hasattr(uow.attempts, "delete"):
        with pytest.raises(ImmutableRecordError):
            uow.attempts.delete()

def test_two_training_records_same_session_and_concept(uow):
    r1 = TrainingRecord(
        student_id="std-1",
        concept_id="c-1",
        session_id="sess-1",
        p_observed=0.75,
        n_answers=4,
        delta_days=2.0,
        counts_before={"n_right": 2, "n_wrong": 1},
        x_before=[1.0, 2.0, 1.0],
        feature_spec_name="raw_counts",
        model_version="hlr_v0_fixed",
        source_event_ids=["evt-1", "evt-2"],
        created_at=NOW
    )
    r2 = TrainingRecord(
        student_id="std-1",
        concept_id="c-1",
        session_id="sess-1",  # duplicate (session_id, concept_id)
        p_observed=0.50,
        n_answers=2,
        delta_days=2.0,
        counts_before={"n_right": 2, "n_wrong": 1},
        x_before=[1.0, 2.0, 1.0],
        feature_spec_name="raw_counts",
        model_version="hlr_v0_fixed",
        source_event_ids=["evt-3"],
        created_at=NOW
    )

    with uow:
        uow.training_records.add(r1)

    with pytest.raises(DuplicateKeyError):
        with uow:
            uow.training_records.add(r2)

def test_check_constraints_training_and_concept_state(uow):
    # p_observed > 1.0
    bad_p = TrainingRecord(
        student_id="std-1",
        concept_id="c-1",
        session_id="sess-bad-1",
        p_observed=1.2,
        n_answers=2,
        delta_days=1.0,
        counts_before={},
        x_before=[1.0, 0.0, 0.0],
        feature_spec_name="raw_counts",
        model_version="hlr_v0_fixed",
        source_event_ids=["e1"],
        created_at=NOW
    )
    with pytest.raises(ConstraintViolationError):
        with uow:
            uow.training_records.add(bad_p)

    # n_answers = 0
    bad_n = TrainingRecord(
        student_id="std-1",
        concept_id="c-1",
        session_id="sess-bad-2",
        p_observed=0.5,
        n_answers=0,
        delta_days=1.0,
        counts_before={},
        x_before=[1.0, 0.0, 0.0],
        feature_spec_name="raw_counts",
        model_version="hlr_v0_fixed",
        source_event_ids=["e1"],
        created_at=NOW
    )
    with pytest.raises(ConstraintViolationError):
        with uow:
            uow.training_records.add(bad_n)

    # n_right < 0
    bad_state = ConceptStateRecord(
        student_id="std-1",
        concept_id="c-1",
        n_right=-1,
        n_wrong=0,
        last_practiced_at=NOW,
        half_life_days=1.0,
        recall_prob_now=0.9,
        next_review_at=NOW,
        model_version="hlr_v0_fixed",
        updated_at=NOW
    )
    with pytest.raises(ConstraintViolationError):
        with uow:
            uow.concept_states.upsert(bad_state)

def test_at_most_one_active_model(uow):
    m1 = ModelVersionRecord(
        id="m-v1",
        name="model1",
        version="1.0",
        theta=[0.0, 1.0, -1.0],
        feature_spec={"name": "raw_counts"},
        training_config={},
        checksum="chk1",
        active=True
    )
    m2 = ModelVersionRecord(
        id="m-v2",
        name="model2",
        version="2.0",
        theta=[0.1, 1.2, -0.9],
        feature_spec={"name": "sqrt_counts"},
        training_config={},
        checksum="chk2",
        active=True
    )

    with uow:
        uow.models.register(m1)
        uow.models.register(m2)

    with uow:
        active = uow.models.get_active()
        assert active is not None
        assert active.id == "m-v2"
        # Only m2 is active, m1 was deactivated
        all_models = uow.models.list_all()
        active_count = sum(1 for m in all_models if m.active)
        assert active_count == 1

def test_rollback_on_failure(uow):
    sess = SessionRecord(id="sess-tx-1", student_id="std-1", started_at=NOW)
    try:
        with uow:
            uow.sessions.create(sess)
            raise RuntimeError("Injected database failure mid-transaction")
    except RuntimeError:
        pass

    with uow:
        assert uow.sessions.get("sess-tx-1") is None
