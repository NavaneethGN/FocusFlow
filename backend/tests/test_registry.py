"""
backend/tests/test_registry.py
Verification tests for Module 10: Model Registry, Gates, Promotion, Rollback, and Shadow Mode.
"""
from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient

from main import app
from repositories.memory import InMemoryUnitOfWork
from hlr.config import HLRConfig
from hlr.features import RAW_SPEC, SQRT_SPEC, FeatureSpec
from hlr.predictor import HLRValidationError
from hlr.updater import ModelArtifact, HLR_V0_FIXED
from ml.model_registry import ModelRegistry, compute_model_checksum
from ml.promotion import promote_model, rollback_model, AUDIT_LOGS

client = TestClient(app)

def test_seeding_first_start():
    uow = InMemoryUnitOfWork()
    registry = ModelRegistry()
    active_rec = registry.seed_default_model(uow)

    assert active_rec.active is True
    assert active_rec.validation_status == "provisional_fixed_weights"
    assert active_rec.evaluation_metrics is None
    assert active_rec.theta == [0.0, 1.0, -1.0]

    all_models = registry.list_models(uow)
    active_models = [m for m in all_models if m.active]
    assert len(active_models) == 1

def test_api_models_reads_from_registry():
    resp = client.get("/api/models")
    assert resp.status_code == 200
    data = resp.json()
    assert "models" in data
    assert "active_model_id" in data
    active_models = [m for m in data["models"] if m.get("active")]
    assert len(active_models) == 1
    # Metrics must remain None for provisional or models without evaluation
    for m in data["models"]:
        assert m.get("metrics") is None

def test_register_candidate():
    uow = InMemoryUnitOfWork()
    registry = ModelRegistry()
    registry.seed_default_model(uow)

    art = ModelArtifact("candidate_v1", [0.15, 1.42, -1.18], SQRT_SPEC, HLRConfig())
    cand = registry.register_candidate(art, uow=uow)

    assert cand.active is False
    assert cand.validation_status == "candidate"
    assert len(cand.checksum) == 64
    assert cand.theta == [0.15, 1.42, -1.18]

def test_spec_mismatch_rejected_at_registration():
    registry = ModelRegistry()
    # 2 weights with 3-feature spec
    with pytest.raises(HLRValidationError):
        bad_art = ModelArtifact("bad", [0.5, 0.5], RAW_SPEC, HLRConfig())
        registry.register_candidate(bad_art)

def test_tampered_theta_fails_checksum():
    uow = InMemoryUnitOfWork()
    registry = ModelRegistry()
    active_rec = registry.seed_default_model(uow)

    # Tamper with stored theta behind the registry in storage
    uow.master_storage["models"][active_rec.id].theta[0] = 999.0

    with pytest.raises(HLRValidationError, match="Tampered model detected"):
        registry.load_active_model(uow, bypass_cache=True)

def test_gate_failure():
    uow = InMemoryUnitOfWork()
    registry = ModelRegistry()
    registry.seed_default_model(uow)

    art = ModelArtifact("worse_cand", [0.5, 0.5, -0.5], RAW_SPEC, HLRConfig())
    # candidate MAE is worse than Leitner baseline
    cand = registry.register_candidate(
        art,
        evaluation_metrics={"mae": 0.25, "leitner_mae": 0.15, "beats_leitner": False},
        uow=uow
    )

    with pytest.raises(HLRValidationError, match="Promotion gate failure"):
        promote_model(cand.id, approver="admin_user", role="admin", uow=uow)

def test_gate_pass_and_activation():
    uow = InMemoryUnitOfWork()
    registry = ModelRegistry()
    registry.seed_default_model(uow)

    art = ModelArtifact("good_cand", [0.15, 1.42, -1.18], SQRT_SPEC, HLRConfig())
    cand = registry.register_candidate(
        art,
        evaluation_metrics={"mae": 0.12, "leitner_mae": 0.18, "beats_leitner": True},
        uow=uow
    )

    promoted = promote_model(cand.id, approver="alice_lead", role="admin", uow=uow)
    assert promoted.active is True
    assert promoted.id == cand.id

    all_models = uow.models.list_all()
    active_models = [m for m in all_models if m.active]
    assert len(active_models) == 1
    assert active_models[0].id == cand.id

def test_authorization_non_admin_cannot_promote():
    uow = InMemoryUnitOfWork()
    registry = ModelRegistry()
    registry.seed_default_model(uow)

    art = ModelArtifact("good_cand", [0.15, 1.42, -1.18], SQRT_SPEC, HLRConfig())
    cand = registry.register_candidate(art, evaluation_metrics={"beats_leitner": True}, uow=uow)

    with pytest.raises(HLRValidationError, match="Unauthorized"):
        promote_model(cand.id, approver="bob_student", role="student", uow=uow)

def test_rollback():
    uow = InMemoryUnitOfWork()
    registry = ModelRegistry()
    v0 = registry.seed_default_model(uow)

    art = ModelArtifact("v1_cand", [0.15, 1.42, -1.18], SQRT_SPEC, HLRConfig())
    cand = registry.register_candidate(art, evaluation_metrics={"beats_leitner": True}, uow=uow)

    promote_model(cand.id, approver="alice", role="admin", uow=uow)
    assert uow.models.get_active().id == cand.id

    # Rollback to v0
    rolled_back = rollback_model(v0.id, approver="alice", role="admin", uow=uow)
    assert rolled_back.id == v0.id
    assert uow.models.get_active().id == v0.id

def test_audit_logging():
    uow = InMemoryUnitOfWork()
    registry = ModelRegistry()
    v0 = registry.seed_default_model(uow)
    cand = registry.register_candidate(
        ModelArtifact("v1", [0.1, 1.2, -1.0], RAW_SPEC, HLRConfig()),
        evaluation_metrics={"beats_leitner": True},
        uow=uow
    )

    audit_count_before = len(AUDIT_LOGS)
    promote_model(cand.id, approver="auditor_jane", role="admin", uow=uow)
    assert len(AUDIT_LOGS) == audit_count_before + 1
    last_entry = AUDIT_LOGS[-1]
    assert last_entry.action == "promote"
    assert last_entry.approver == "auditor_jane"
    assert last_entry.model_id == cand.id

def test_shadow_mode_storage():
    registry = ModelRegistry()
    registry.record_shadow_prediction(
        session_id="sess-100",
        student_id="std-1",
        concept_id="c-bfs",
        active_prediction=0.99,
        candidate_model_id="cand-v1",
        candidate_prediction=0.88
    )
    shadows = registry.get_shadow_predictions(session_id="sess-100")
    assert len(shadows) == 1
    assert shadows[0]["candidate_model_id"] == "cand-v1"
    assert shadows[0]["candidate_p"] == 0.88
