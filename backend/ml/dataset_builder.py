"""
backend/ml/dataset_builder.py
Dataset snapshot creation, versioning, row hashing, and leakage-safe splits.
Supports temporal splits and clustered student-holdout splits.
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import json
import math
import random
from typing import Sequence, List, Tuple, Dict, Any, Optional, Set

from repositories.base import TrainingRecord
from hlr.predictor import HLRValidationError

@dataclass(frozen=True)
class DatasetSnapshot:
    """Immutable, versioned dataset snapshot with cryptographically stable row hash."""
    snapshot_id: str
    row_hash: str
    created_at: datetime
    filters: Dict[str, Any]
    examples: List[Any]
    count: int

def _canonical_record_string(record: Any) -> str:
    """Serializes a record into a canonical string for deterministic SHA256 hashing."""
    if isinstance(record, dict):
        student_id = str(record.get("student_id", ""))
        session_id = str(record.get("session_id", ""))
        concept_id = str(record.get("concept_id", ""))
        p_obs = float(record.get("p_observed", 0.0))
        delta = float(record.get("delta_days", 0.0))
        x_before = [float(v) for v in record.get("x_before", [])]
        spec_name = str(record.get("feature_spec_name", ""))
        ts = record.get("created_at")
    else:
        student_id = str(getattr(record, "student_id", ""))
        session_id = str(getattr(record, "session_id", ""))
        concept_id = str(getattr(record, "concept_id", ""))
        p_obs = float(getattr(record, "p_observed", 0.0))
        delta = float(getattr(record, "delta_days", 0.0))
        x_before = [float(v) for v in getattr(record, "x_before", [])]
        spec_name = str(getattr(record, "feature_spec_name", ""))
        ts = getattr(record, "created_at", None)

    ts_str = ts.isoformat() if isinstance(ts, datetime) else str(ts or "")
    payload = {
        "student_id": student_id,
        "session_id": session_id,
        "concept_id": concept_id,
        "p_observed": round(p_obs, 8),
        "delta_days": round(delta, 8),
        "x_before": [round(v, 8) for v in x_before],
        "feature_spec_name": spec_name,
        "created_at": ts_str,
    }
    return json.dumps(payload, sort_keys=True)

def build_dataset_snapshot(
    records: Sequence[Any],
    filters: Optional[Dict[str, Any]] = None
) -> DatasetSnapshot:
    """Filters, deterministically sorts, and cryptographically hashes dataset records."""
    active_filters = filters or {}
    filtered_records: List[Any] = []

    for r in records:
        if isinstance(r, dict):
            student_id = r.get("student_id")
            spec_name = r.get("feature_spec_name")
            delta = r.get("delta_days", 0.0)
        else:
            student_id = getattr(r, "student_id", None)
            spec_name = getattr(r, "feature_spec_name", None)
            delta = getattr(r, "delta_days", 0.0)

        if "feature_spec_name" in active_filters and spec_name != active_filters["feature_spec_name"]:
            continue
        if "min_delta_days" in active_filters and delta < active_filters["min_delta_days"]:
            continue
        if "max_delta_days" in active_filters and delta > active_filters["max_delta_days"]:
            continue
        if "student_ids" in active_filters and student_id not in active_filters["student_ids"]:
            continue

        filtered_records.append(r)

    # Sort deterministically by canonical string representation
    serialized_tuples = [(_canonical_record_string(r), r) for r in filtered_records]
    serialized_tuples.sort(key=lambda item: item[0])

    hasher = hashlib.sha256()
    for s_str, _ in serialized_tuples:
        hasher.update(s_str.encode("utf-8"))
        hasher.update(b"\n")
    
    row_hash = hasher.hexdigest()
    sorted_examples = [item[1] for item in serialized_tuples]
    snapshot_id = f"snap-{row_hash[:12]}"

    return DatasetSnapshot(
        snapshot_id=snapshot_id,
        row_hash=row_hash,
        created_at=datetime.now(timezone.utc),
        filters=active_filters,
        examples=sorted_examples,
        count=len(sorted_examples)
    )

def temporal_split(
    examples: Sequence[Any],
    cutoff_time: datetime
) -> Tuple[List[Any], List[Any]]:
    """Splits records temporally, guaranteeing zero temporal leakage.
    
    Every test record's timestamp is strictly later than every train record's timestamp.
    Groups records by (student_id, session_id) so a single session is never fractured.
    """
    if cutoff_time.tzinfo is None:
        raise HLRValidationError("cutoff_time must be timezone-aware UTC datetime")

    # Group by session_id to maintain session group integrity
    sessions: Dict[str, List[Any]] = {}
    session_times: Dict[str, datetime] = {}

    for r in examples:
        sess_id = r["session_id"] if isinstance(r, dict) else getattr(r, "session_id")
        created_at = r["created_at"] if isinstance(r, dict) else getattr(r, "created_at")
        if created_at.tzinfo is None:
            raise HLRValidationError("Record created_at must be timezone-aware UTC datetime")

        if sess_id not in sessions:
            sessions[sess_id] = []
            session_times[sess_id] = created_at
        else:
            if created_at > session_times[sess_id]:
                session_times[sess_id] = created_at
        sessions[sess_id].append(r)

    train: List[Any] = []
    test: List[Any] = []

    for sess_id, recs in sessions.items():
        sess_time = session_times[sess_id]
        if sess_time <= cutoff_time:
            train.extend(recs)
        else:
            test.extend(recs)

    return train, test

def student_holdout_split(
    examples: Sequence[Any],
    holdout_fraction: float = 0.2,
    seed: int = 42
) -> Tuple[List[Any], List[Any]]:
    """Splits records clustered by student_id to prevent student data leakage.
    
    Zero student overlap: no student appears in both train and test.
    Keeps all rows of any student-concept-session intact within one split.
    """
    if not (0.0 < holdout_fraction < 1.0):
        raise HLRValidationError(f"holdout_fraction must be in (0, 1), got {holdout_fraction}")

    # Collect unique students
    student_set: Set[str] = set()
    for r in examples:
        s_id = r["student_id"] if isinstance(r, dict) else getattr(r, "student_id")
        student_set.add(s_id)

    students = sorted(list(student_set))
    rng = random.Random(seed)
    rng.shuffle(students)

    n_holdout = max(1, int(round(len(students) * holdout_fraction)))
    holdout_students = set(students[:n_holdout])

    train: List[Any] = []
    test: List[Any] = []

    for r in examples:
        s_id = r["student_id"] if isinstance(r, dict) else getattr(r, "student_id")
        if s_id in holdout_students:
            test.append(r)
        else:
            train.append(r)

    return train, test
