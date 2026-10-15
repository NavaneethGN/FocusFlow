"""
backend/ml/simulator.py
Synthetic learner simulator for generating ground-truth HLR training datasets.
Reproducible, seedable, and supports exact and sampled Bernoulli draws.
"""
from datetime import datetime, timezone, timedelta
from typing import Sequence, List, Optional, Dict, Any
import numpy as np

from hlr.features import ConceptCounts, FeatureSpec, extract_features, RAW_SPEC, SQRT_SPEC, SQRT_DIFFICULTY_SPEC
from hlr.predictor import predict_half_life, predict_recall
from hlr.updater import apply_outcome
from repositories.base import TrainingRecord

DEFAULT_LAUNCH_THETA = [0.0, 1.0, -1.0]
DEFAULT_TRAINED_THETA = [0.15, 1.42, -1.18]

def simulate_learners(
    theta_true: Sequence[float],
    feature_spec: FeatureSpec,
    n_students: int = 10,
    n_concepts: int = 5,
    n_sessions: int = 10,
    questions_per_session: int = 5,
    interval_distribution: str = "lognormal",
    label_mode: str = "session_fraction",
    exact_mode: bool = False,
    seed: Optional[int] = 42,
    difficulty_by_concept: Optional[Dict[str, Any]] = None,
    concepts_per_session: Optional[int] = None
) -> List[TrainingRecord]:
    """Generates synthetic training records matching the production database schema.
    
    - label_mode: 'session_fraction' (fraction of questions answered correctly)
                  or 'binary' (single recall outcome, n_answers = 1)
    - exact_mode: returns theoretical p_true directly without noise
    """
    rng = np.random.default_rng(seed)
    records: List[TrainingRecord] = []
    base_time = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)

    for s_idx in range(n_students):
        student_id = f"std-sim-{s_idx:04d}"

        concept_counts: Dict[str, ConceptCounts] = {
            f"c-sim-{c_idx:03d}": ConceptCounts(0, 0) for c_idx in range(n_concepts)
        }
        last_times: Dict[str, datetime] = {}

        current_time = base_time

        for sess_idx in range(n_sessions):
            session_id = f"sess-sim-{s_idx:04d}-{sess_idx:04d}"

            if concepts_per_session is None:
                active_cids = list(concept_counts.keys())
            else:
                active_cids = rng.choice(
                    list(concept_counts.keys()),
                    size=min(concepts_per_session, n_concepts),
                    replace=False
                )

            for cid in active_cids:
                counts = concept_counts[cid]
                context = None
                if difficulty_by_concept and cid in difficulty_by_concept:
                    context = {"difficulty_score": difficulty_by_concept[cid], "difficulty": difficulty_by_concept[cid]}
                elif feature_spec.name == "sqrt_counts_difficulty":
                    diff_val = float((int(cid.split("-")[-1]) % 3) - 1)
                    context = {"difficulty_score": diff_val}

                if cid not in last_times:
                    # Cold start: first practice produces NO training record
                    n_ans = 1 if label_mode == "binary" else questions_per_session
                    n_corr = max(1, n_ans - 1)
                    concept_counts[cid] = apply_outcome(counts, n_corr, n_ans - n_corr)
                    last_times[cid] = current_time
                    continue

                x_before = extract_features(counts, feature_spec, context)
                h_true = predict_half_life(theta_true, x_before)

                # Draw delta_days
                if interval_distribution == "adaptive_review":
                    target_p = float(rng.uniform(0.65, 0.75))
                    delta_days = float(-h_true * np.log2(target_p))
                    delta_days = max(0.01, min(delta_days, 180.0))
                elif interval_distribution == "lognormal":
                    # Spans across 3+ orders of magnitude (~0.05 to ~60 days)
                    delta_days = float(np.exp(rng.normal(loc=0.8, scale=1.3)))
                    delta_days = max(0.01, min(delta_days, 180.0))
                elif interval_distribution == "exponential":
                    delta_days = float(rng.exponential(scale=3.0))
                    delta_days = max(0.01, min(delta_days, 180.0))
                else:
                    delta_days = float(rng.uniform(0.5, 14.0))

                event_time = last_times[cid] + timedelta(days=delta_days)
                p_true = predict_recall(h_true, delta_days)

                n_ans = 1 if label_mode == "binary" else questions_per_session

                if exact_mode:
                    p_obs = p_true
                    n_corr = int(round(p_obs * n_ans))
                else:
                    if label_mode == "binary":
                        n_corr = int(rng.random() < p_true)
                        p_obs = float(n_corr)
                    else:
                        n_corr = int(rng.binomial(n_ans, p_true))
                        p_obs = float(n_corr) / float(n_ans)

                rec = TrainingRecord(
                    student_id=student_id,
                    concept_id=cid,
                    session_id=session_id,
                    p_observed=p_obs,
                    n_answers=n_ans,
                    delta_days=delta_days,
                    counts_before={
                        "n_right": counts.n_right,
                        "n_wrong": counts.n_wrong
                    },
                    x_before=x_before,
                    feature_spec_name=feature_spec.name,
                    model_version="simulator_truth",
                    source_event_ids=[f"evt-sim-{s_idx}-{sess_idx}-{cid}"],
                    created_at=event_time,
                    label_definition_version="1.0"
                )
                records.append(rec)

                # Update counts for future sessions
                concept_counts[cid] = apply_outcome(counts, n_corr, n_ans - n_corr)
                last_times[cid] = event_time

            # Advance current time for student
            current_time += timedelta(days=float(rng.uniform(0.2, 2.0)))

    return records
