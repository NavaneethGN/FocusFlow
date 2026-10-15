"""
backend/jobs/monitoring_job.py
Production monitoring job calculating bounds saturation, non-finite values,
and telemetry alerts for active models and concept states.
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone
import math
from typing import Sequence, List, Dict, Any, Optional

from hlr.config import HLRConfig

@dataclass
class MonitoringReport:
    active_model_version: str
    total_states: int
    share_at_bounds: float
    non_finite_count: int
    duplicate_event_rate: float
    alerts: List[str]
    generated_at: str

def run_monitoring_job(
    states: Sequence[Any],
    attempts: Sequence[Any],
    active_model_version: str,
    config: Optional[HLRConfig] = None
) -> MonitoringReport:
    """Computes health telemetry and raises alerts on anomalies."""
    cfg = config or HLRConfig()
    alerts: List[str] = []

    total_states = len(states)
    at_bounds_count = 0
    non_finite_count = 0

    for s in states:
        if isinstance(s, dict):
            h = float(s.get("half_life_days", 1.0))
            p = float(s.get("p_hat", 0.5))
        else:
            h = float(getattr(s, "half_life_days", 1.0))
            p = float(getattr(s, "recall_prob_now", getattr(s, "p_hat", 0.5)))

        if not math.isfinite(h) or not math.isfinite(p):
            non_finite_count += 1
            continue

        if abs(h - cfg.h_min_days) < 1e-5 or abs(h - cfg.h_max_days) < 1e-5:
            at_bounds_count += 1

    share_bounds = (at_bounds_count / float(total_states)) if total_states > 0 else 0.0
    if share_bounds > 0.30:
        alerts.append(f"Alert: {share_bounds:.1%} of concept states saturated at half-life bounds [h_min, h_max]")

    if non_finite_count > 0:
        alerts.append(f"Critical Alert: {non_finite_count} concept states contain non-finite predictions")

    # Duplicate events check
    event_ids = set()
    dup_count = 0
    for a in attempts:
        e_id = a.get("event_id") if isinstance(a, dict) else getattr(a, "event_id", None)
        if e_id:
            if e_id in event_ids:
                dup_count += 1
            else:
                event_ids.add(e_id)

    dup_rate = (dup_count / float(len(attempts))) if len(attempts) > 0 else 0.0
    if dup_rate > 0.05:
        alerts.append(f"Alert: Duplicate event rate {dup_rate:.2%} exceeds 5% threshold")

    return MonitoringReport(
        active_model_version=active_model_version,
        total_states=total_states,
        share_at_bounds=round(share_bounds, 4),
        non_finite_count=non_finite_count,
        duplicate_event_rate=round(dup_rate, 4),
        alerts=alerts,
        generated_at=datetime.now(timezone.utc).isoformat()
    )
