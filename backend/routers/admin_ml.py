"""
backend/routers/admin_ml.py
Administrative API router for machine learning lifecycle management.
Secured with admin role authorization guard.
"""
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, Header, HTTPException, Depends, status

from repositories import get_uow
from ml.model_registry import GLOBAL_REGISTRY
from ml.promotion import promote_model, rollback_model, AUDIT_LOGS
from jobs.training_job import run_training_job, JOB_RUNS
from hlr.predictor import HLRValidationError

router = APIRouter(prefix="/api/admin", tags=["admin_ml"])

def require_admin(x_role: Optional[str] = Header(None, alias="X-Role")) -> str:
    """Enforces admin authorization; returns 403 for non-admin callers."""
    if not x_role or x_role.lower() != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Admin role required for ML administration endpoints"
        )
    return x_role

@router.get("/models")
def list_admin_models(role: str = Depends(require_admin)) -> Dict[str, Any]:
    """Lists all registered model versions."""
    with get_uow() as uow:
        models = GLOBAL_REGISTRY.list_models(uow)
        return {
            "total": len(models),
            "models": [
                {
                    "id": m.id,
                    "name": m.name,
                    "version": m.version,
                    "active": m.active,
                    "status": m.validation_status,
                    "theta": m.theta,
                    "feature_spec": m.feature_spec,
                    "metrics": m.evaluation_metrics,
                    "checksum": m.checksum
                } for m in models
            ]
        }

@router.get("/training-runs")
def list_training_runs(role: str = Depends(require_admin)) -> List[Dict[str, Any]]:
    """Lists all historical and current job runs."""
    return [
        {
            "job_name": run.job_name,
            "window_key": run.window_key,
            "status": run.status,
            "details": run.details,
            "started_at": run.started_at.isoformat(),
            "completed_at": run.completed_at.isoformat() if run.completed_at else None,
            "error_message": run.error_message
        } for run in JOB_RUNS.values()
    ]

@router.post("/training-runs/start")
def trigger_training_run(role: str = Depends(require_admin)) -> Dict[str, Any]:
    """Manually triggers an offline training run over persisted training records."""
    with get_uow() as uow:
        records = uow.training_records.list_all()
        window_key = f"manual-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
        run = run_training_job(records, window_key=window_key, uow=uow)
        return {
            "job_name": run.job_name,
            "window_key": run.window_key,
            "status": run.status,
            "details": run.details,
            "error_message": run.error_message
        }

@router.post("/models/{model_id}/activate")
def activate_model_endpoint(
    model_id: str,
    role: str = Depends(require_admin)
) -> Dict[str, Any]:
    """Promotes a candidate model to active status, running multi-stage gates."""
    with get_uow() as uow:
        try:
            promoted = promote_model(model_id=model_id, approver="admin_api", role=role, uow=uow)
            return {
                "success": True,
                "message": f"Model '{model_id}' promoted to active",
                "model_id": promoted.id,
                "active": promoted.active
            }
        except HLRValidationError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

@router.post("/models/{model_id}/rollback")
def rollback_model_endpoint(
    model_id: str,
    role: str = Depends(require_admin)
) -> Dict[str, Any]:
    """Rolls back the active model to an earlier registered version."""
    with get_uow() as uow:
        try:
            rolled_back = rollback_model(to_model_id=model_id, approver="admin_api", role=role, uow=uow)
            return {
                "success": True,
                "message": f"Active model rolled back to '{model_id}'",
                "model_id": rolled_back.id,
                "active": rolled_back.active
            }
        except HLRValidationError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
