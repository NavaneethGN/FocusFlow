"""
backend/tests/test_difficulty_feature.py
Verification tests for Module 14: Difficulty Feature (sqrt_counts_difficulty)
"""
import copy
import math
from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient

import main
from main import app, init_db, set_clock, reset_clock, db_concepts, db_training_records
from hlr.config import HLRConfig
from hlr.features import (
    ConceptCounts,
    RAW_SPEC,
    SQRT_SPEC,
    SQRT_DIFFICULTY_SPEC,
    extract_features,
    spec_hash,
    DATA_QUALITY_METRICS
)
from hlr.predictor import HLRValidationError, predict_half_life, predict_recall
from hlr.updater import ModelArtifact
from hlr.trainer import train_hlr, TrainerConfig
from hlr.evaluation import compute_mae
from ml.simulator import simulate_learners
from ml.model_registry import ModelRegistry, GLOBAL_REGISTRY
from ml.promotion import run_promotion_gates, promote_model
from repositories import get_uow
from repositories.memory import InMemoryUnitOfWork

client = TestClient(app)

FIXED_TIME = datetime(2026, 10, 15, 12, 0, 0, tzinfo=timezone.utc)

@pytest.fixture(autouse=True)
def setup_teardown():
    set_clock(lambda: FIXED_TIME)
    init_db()
    yield
    reset_clock()
    init_db()

def test_new_vector():
    """1. New vector: 3 right, 1 wrong, Hard gives [1, 1.7320508, 1, 1]."""
    counts = ConceptCounts(3, 1)
    vec_hard = extract_features(counts, SQRT_DIFFICULTY_SPEC, {"difficulty": "Hard"})
    assert len(vec_hard) == 4
    assert vec_hard[0] == 1.0
    assert abs(vec_hard[1] - 1.7320508) < 1e-5
    assert vec_hard[2] == 1.0
    assert vec_hard[3] == 1.0

    vec_med = extract_features(counts, SQRT_DIFFICULTY_SPEC, {"difficulty": "Medium"})
    assert vec_med[3] == 0.0

    vec_easy = extract_features(counts, SQRT_DIFFICULTY_SPEC, {"difficulty": "Easy"})
    assert vec_easy[3] == -1.0

def test_older_specs_unaffected():
    """2. Older specs: raw_counts and sqrt_counts vectors identical to before for every input."""
    counts = ConceptCounts(3, 1)
    ctx = {"difficulty": "Hard"}

    raw_vec = extract_features(counts, RAW_SPEC, ctx)
    assert raw_vec == [1.0, 3.0, 1.0]

    sqrt_vec = extract_features(counts, SQRT_SPEC, ctx)
    assert len(sqrt_vec) == 3
    assert sqrt_vec[0] == 1.0
    assert abs(sqrt_vec[1] - math.sqrt(3.0)) < 1e-12
    assert sqrt_vec[2] == 1.0

def test_spec_hash_differs():
    """3. Spec hash differs from sqrt_counts."""
    h_diff = spec_hash(SQRT_DIFFICULTY_SPEC)
    h_sqrt = spec_hash(SQRT_SPEC)
    h_raw = spec_hash(RAW_SPEC)
    assert h_diff != h_sqrt
    assert h_diff != h_raw
    assert isinstance(h_diff, str) and len(h_diff) == 64

def test_theta_length_mismatch():
    """4. Theta length: a 3-weight theta with the 4-feature spec is rejected."""
    with pytest.raises(HLRValidationError, match="dimension mismatch"):
        ModelArtifact("test_3w", [0.0, 1.0, -1.0], SQRT_DIFFICULTY_SPEC, HLRConfig())

    uow = InMemoryUnitOfWork()
    registry = ModelRegistry()
    with pytest.raises(HLRValidationError):
        # Even if circumvented, post_init in ModelArtifact blocks construction
        artifact = ModelArtifact("bad_dim", [0.0, 1.0], SQRT_DIFFICULTY_SPEC, HLRConfig())
        registry.register_candidate(artifact, uow=uow)

def test_history_safety():
    """5. History safety: changing a concept's difficulty later does not change stored x_before."""
    # Activate a 4-feature model in the registry
    with get_uow() as uow:
        active_baseline = uow.models.get_active() or GLOBAL_REGISTRY.seed_default_model(uow)
        baseline_id = active_baseline.id

        four_feature_artifact = ModelArtifact(
            "hlr_diff_active",
            [0.1, 0.9, -0.9, -0.4],
            SQRT_DIFFICULTY_SPEC,
            HLRConfig()
        )
        cand = GLOBAL_REGISTRY.register_candidate(four_feature_artifact, uow=uow)
        # Promote it to active
        promote_model(
            cand.id,
            approver="admin_test",
            role="admin",
            uow=uow,
            gate_override_reasons=["Test activation for history safety"]
        )

    # Concept starts as Hard
    cid = "c-ai-1"
    main.db_concepts[cid]["difficulty"] = "Hard"
    main.db_concepts[cid]["n_right"] = 2
    main.db_concepts[cid]["n_wrong"] = 1
    main.db_concepts[cid]["last_practiced_at"] = (FIXED_TIME).isoformat()

    sess_id = "sess-history-001"
    main.db_training_records.clear()

    # Answer a question and complete session
    ans = client.post(
        f"/api/sessions/{sess_id}/answers",
        headers={"X-Student-Id": "std-hist"},
        json={
            "event_id": "evt-hist-1",
            "concept_id": cid,
            "question_id": "q-1",
            "selected_index": 0,
            "response_time_ms": 1000
        }
    )
    assert ans.status_code == 200

    comp = client.post(f"/api/sessions/{sess_id}/complete", headers={"X-Student-Id": "std-hist"})
    assert comp.status_code == 200

    assert len(main.db_training_records) == 1
    saved_x = main.db_training_records[0]["x_before"]
    assert len(saved_x) == 4
    assert saved_x[3] == 1.0  # Hard was +1.0

    # Now change concept difficulty in database to Easy (-1.0)
    main.db_concepts[cid]["difficulty"] = "Easy"

    # Stored training record x_before must remain unchanged (+1.0)
    assert main.db_training_records[0]["x_before"][3] == 1.0

    # Reset active model back to baseline
    with get_uow() as uow:
        promote_model(baseline_id, approver="admin_test", role="admin", uow=uow, gate_override_reasons=["Reset"])

def test_recovery_true_difficulty_weight():
    """6. Recovery: simulate with a true difficulty weight of -0.5: trainer recovers it within 0.15."""
    true_theta = [0.20, 0.80, -0.80, -0.50]
    records = simulate_learners(
        theta_true=true_theta,
        feature_spec=SQRT_DIFFICULTY_SPEC,
        n_students=600,
        n_concepts=6,
        n_sessions=8,
        questions_per_session=6,
        exact_mode=True,
        seed=101
    )
    assert len(records) > 2000

    cfg = TrainerConfig(
        max_iterations=120,
        learning_rate=0.25,
        alpha=0.0,
        lambda_=0.0001,
        seed=101
    )
    init_theta = [0.0, 0.5, -0.5, 0.0]
    artifact, report = train_hlr(records, init_theta, SQRT_DIFFICULTY_SPEC, cfg)

    recovered_diff_weight = artifact.theta[3]
    # Check within 0.15 of -0.50
    assert abs(recovered_diff_weight - (-0.50)) < 0.15, f"Recovered {recovered_diff_weight} not within 0.15 of -0.50"

def test_value_of_feature_beats_3_feature_model():
    """7. Value of the feature: on data where Hard concepts decay faster, 4-feature model beats 3-feature model."""
    true_theta = [0.20, 0.80, -0.80, -0.75]
    all_records = simulate_learners(
        theta_true=true_theta,
        feature_spec=SQRT_DIFFICULTY_SPEC,
        n_students=500,
        n_concepts=6,
        n_sessions=8,
        exact_mode=False,
        seed=42
    )

    # 80/20 train/test split
    split_idx = int(0.8 * len(all_records))
    train_records = all_records[:split_idx]
    test_records = all_records[split_idx:]

    cfg = TrainerConfig(max_iterations=80, learning_rate=0.20, alpha=0.0, lambda_=0.001)

    # Train 4-feature model
    art_4, _ = train_hlr(train_records, [0.0, 0.5, -0.5, 0.0], SQRT_DIFFICULTY_SPEC, cfg)

    # Create 3-feature equivalent records for 3-feature model
    train_records_3 = []
    test_records_3 = []
    for r in train_records:
        r3 = copy.deepcopy(r)
        r3.x_before = r.x_before[:3]
        train_records_3.append(r3)
    for r in test_records:
        r3 = copy.deepcopy(r)
        r3.x_before = r.x_before[:3]
        test_records_3.append(r3)

    art_3, _ = train_hlr(train_records_3, [0.0, 0.5, -0.5], SQRT_SPEC, cfg)

    y_true = [r.p_observed for r in test_records]
    y_pred_4 = [predict_recall(predict_half_life(art_4.theta, r.x_before), r.delta_days) for r in test_records]
    y_pred_3 = [predict_recall(predict_half_life(art_3.theta, r.x_before), r.delta_days) for r in test_records_3]

    mae_4 = compute_mae(y_true, y_pred_4)
    mae_3 = compute_mae(y_true, y_pred_3)

    assert mae_4 < mae_3, f"4-feature MAE ({mae_4:.4f}) should beat 3-feature MAE ({mae_3:.4f})"

def test_no_value_gate_does_not_promote():
    """8. No value: on data without a difficulty effect, the gate does not promote it."""
    uow = InMemoryUnitOfWork()
    registry = ModelRegistry()
    registry.seed_default_model(uow)
    active_m = uow.models.get_active()

    # Create candidate with poor evaluation metrics (does not beat Leitner)
    art = ModelArtifact("cand_weak", [0.0, 0.5, -0.5, 0.0], SQRT_DIFFICULTY_SPEC, HLRConfig())
    cand = registry.register_candidate(
        art,
        evaluation_metrics={"mae": 0.28, "leitner_mae": 0.16, "beats_leitner": False},
        uow=uow
    )

    report = run_promotion_gates(cand, active_m)
    assert report.passed is False
    assert any("does not beat Leitner" in r for r in report.reasons)

def test_missing_difficulty_maps_to_zero_and_increments_counter():
    """9. Missing difficulty: maps to 0 and increments the data-quality counter."""
    DATA_QUALITY_METRICS["missing_difficulty_count"] = 0
    counts = ConceptCounts(2, 1)

    # Missing context entirely
    v1 = extract_features(counts, SQRT_DIFFICULTY_SPEC, None)
    assert v1[3] == 0.0
    assert DATA_QUALITY_METRICS["missing_difficulty_count"] == 1

    # Missing difficulty key in context
    v2 = extract_features(counts, SQRT_DIFFICULTY_SPEC, {"other_key": 123})
    assert v2[3] == 0.0
    assert DATA_QUALITY_METRICS["missing_difficulty_count"] == 2

    # Unrecognized difficulty label
    v3 = extract_features(counts, SQRT_DIFFICULTY_SPEC, {"difficulty": "SuperExtreme"})
    assert v3[3] == 0.0
    assert DATA_QUALITY_METRICS["missing_difficulty_count"] == 3
