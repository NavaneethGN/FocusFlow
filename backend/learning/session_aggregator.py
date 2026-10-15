"""
backend/learning/session_aggregator.py
Groups and aggregates scored attempts by concept.
Deduplicates replayed event_ids and prevents division by zero.
"""
from dataclasses import dataclass
from typing import Sequence, Dict, Any, List

@dataclass
class ConceptSessionStats:
    concept_id: str
    correct: int
    total: int
    p_session: float
    event_ids: List[str]

def aggregate_session_attempts(attempts: Sequence[Dict[str, Any]]) -> Dict[str, ConceptSessionStats]:
    """Groups attempts by concept_id, deduplicating by event_id.
    
    Skips concepts with 0 scored answers to avoid division by zero.
    """
    seen_events = set()
    grouped: Dict[str, Dict[str, Any]] = {}

    for a in attempts:
        event_id = a.get("event_id")
        if not event_id or event_id in seen_events:
            continue
        seen_events.add(event_id)

        cid = a.get("concept_id")
        if not cid:
            continue

        if cid not in grouped:
            grouped[cid] = {"correct": 0, "total": 0, "event_ids": []}

        grouped[cid]["total"] += 1
        if a.get("is_correct") or a.get("correct"):
            grouped[cid]["correct"] += 1
        grouped[cid]["event_ids"].append(event_id)

    results: Dict[str, ConceptSessionStats] = {}
    for cid, data in grouped.items():
        if data["total"] == 0:
            continue
        p = float(data["correct"]) / float(data["total"])
        results[cid] = ConceptSessionStats(
            concept_id=cid,
            correct=data["correct"],
            total=data["total"],
            p_session=p,
            event_ids=data["event_ids"]
        )

    return results
