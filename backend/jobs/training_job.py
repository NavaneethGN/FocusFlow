"""
backend/jobs/training_job.py
Automated HLR candidate training job with data-readiness gates and concurrency locking.
Trains candidate models and registers them in the model registry without activating them.
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone
import math
from typing import Sequence, List, Dict, Any, Optional, Tuple

from repositories.base import UnitOfWork, TrainingRecord
from hlr.features import RAW_SPEC, SQRT_SPEC
from hlr.trainer import train_hlr, TrainerConfig
from ml.model_registry import GLOBAL_REGISTRY

@dataclass
class JobRunRecord:
    job_name: str
    window_key: str
    status: str  # 'running', 'completed', 'skipped', 'failed'
    details: Dict[str, Any]
    started_at: datetime
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None

# In-memory job runs store with atomic window locking
JOB_RUNS: Dict[Tuple[str, str], JobRunRecord] = {}

def acquire_job_lock(job_name: str, window_key: str) -> Optional[JobRunRecord]:
    """Acquires lock for (job_name, window_key). Returns None if already running or completed."""
    key = (job_name, window_key)
    existing = JOB_RUNS.get(key)
    if existing and existing.status in ("running", "completed"):
        return None

    run = JobRunRecord(
        job_name=job_name,
        window_key=window_key,
        status="running",
        details={},
        started_at=datetime.now(timezone.utc)
    )
    JOB_RUNS[key] = run
    return run

def check_data_readiness(
    records: Sequence[Any],
    min_students: int = 5,
    min_examples: int = 40,
    max_dirty_rate: float = 0.05
) -> Tuple[bool, str, List[Any]]:
    """Evaluates whether dataset meets quality and volume requirements for training."""
    if len(records) < min_examples:
        return False, f"Insufficient examples: {len(records)} < {min_examples}", []

    valid_records: List[Any] = []
    dirty_count = 0
    students = set()
    deltas = []

    for r in records:
        if isinstance(r, dict):
            p = r.get("p_observed")
            delta = r.get("delta_days")
            s_id = r.get("student_id")
            x = r.get("x_before", [])
        else:
            p = getattr(r, "p_observed", None)
            delta = getattr(r, "delta_days", None)
            s_id = getattr(r, "student_id", None)
            x = getattr(r, "x_before", [])

        # Check for non-finite or invalid numbers
        is_invalid = (
            p is None or not isinstance(p, (int, float)) or not (0.0 <= p <= 1.0) or math.isnan(p) or
            delta is None or not isinstance(delta, (int, float)) or delta <= 0 or math.isnan(delta) or
            any(not isinstance(v, (int, float)) or math.isnan(v) for v in x)
        )

        if is_invalid:
            dirty_count += 1
        else:
            valid_records.append(r)
            if s_id:
                students.add(s_id)
            deltas.append(delta)

    dirty_rate = dirty_count / float(len(records))
    if dirty_rate > max_dirty_rate:
        return False, f"Dirty data rate {dirty_rate:.2%} exceeds {max_dirty_rate:.2%} limit", []

    if len(students) < min_students:
        return False, f"Insufficient unique students: {len(students)} < {min_students}", []

    if len(deltas) > 0 and (max(deltas) - min(deltas)) < 0.1:
        return False, "Insufficient variation in elapsed time (delta_days)", []

    return True, "Data readiness gates passed", valid_records

def run_training_job(
    records: Sequence[Any],
    window_key: str,
    uow: UnitOfWork,
    feature_spec = RAW_SPEC,
    initial_theta = None,
    config: Optional[TrainerConfig] = None
) -> JobRunRecord:
    """Executes training job inside locked window. Registers candidate model, never activates."""
    lock = acquire_job_lock("training_job", window_key)
    if lock is None:
        return JobRunRecord(
            job_name="training_job",
            window_key=window_key,
            status="skipped",
            details={"reason": "Job already running or completed for window"},
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc)
        )

    try:
        is_ready, reason, valid_records = check_data_readiness(records)
        if not is_ready:
            lock.status = "skipped"
            lock.details = {"reason": reason}
            lock.completed_at = datetime.now(timezone.utc)
            return lock

        init_th = initial_theta or [0.1, 0.8, -0.8]
        cfg = config or TrainerConfig(max_iterations=60, learning_rate=0.15, alpha=0.0, lambda_=0.001)

        artifact, report = train_hlr(valid_records, init_th, feature_spec, cfg)

        # Register candidate in registry (active remains False!)
        cand_record = GLOBAL_REGISTRY.register_candidate(
            artifact=artifact,
            training_report=report,
            uow=uow
        )

        lock.status = "completed"
        lock.details = {
            "candidate_id": cand_record.id,
            "trained_theta": cand_record.theta,
            "stopped_iteration": report.stopped_iteration,
            "losses": [report.losses[0], report.losses[-1]]
        }
        lock.completed_at = datetime.now(timezone.utc)
        return lock

    except Exception as exc:
        lock.status = "failed"
        lock.error_message = str(exc)
        lock.completed_at = datetime.now(timezone.utc)
        return lock
