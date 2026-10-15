# backend/repositories
import os
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
    RepositoryError,
    DuplicateKeyError,
    ConstraintViolationError,
    ConcurrencyError,
    ImmutableRecordError,
)
from .memory import InMemoryUnitOfWork

_POSTGRES_UOW_FACTORY = None

def set_postgres_factory(factory):
    global _POSTGRES_UOW_FACTORY
    _POSTGRES_UOW_FACTORY = factory

_GLOBAL_MEMORY_UOW = InMemoryUnitOfWork()

def get_uow() -> UnitOfWork:
    backend = os.getenv("REPO_BACKEND", "memory").lower()
    if backend == "postgres":
        if _POSTGRES_UOW_FACTORY is None:
            raise RuntimeError("Postgres UOW requested but no factory configured")
        return _POSTGRES_UOW_FACTORY()
    return _GLOBAL_MEMORY_UOW

__all__ = [
    "AttemptRecord",
    "SessionRecord",
    "ConceptStateRecord",
    "PracticeHistoryRecord",
    "TrainingRecord",
    "ModelVersionRecord",
    "AttemptRepo",
    "SessionRepo",
    "ConceptStateRepo",
    "PracticeHistoryRepo",
    "TrainingRecordRepo",
    "ModelRepo",
    "UnitOfWork",
    "RepositoryError",
    "DuplicateKeyError",
    "ConstraintViolationError",
    "ConcurrencyError",
    "ImmutableRecordError",
    "InMemoryUnitOfWork",
    "get_uow",
    "set_postgres_factory",
]
