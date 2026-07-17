from __future__ import annotations

from typing import Any, Callable

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status

from app.dependencies import get_db_path
from app.models import UserRole
from app.routes.ui.utils import get_current_ui_user

from . import cassandra, ceph, elasticsearch, kubernetes, prometheus, vcenter
from .job_store import _create_connector_job, _get_connector_job
from .registry import ASSET_TYPES, CONNECTOR_NAMES, CONNECTOR_SCHEMAS, parse_connector_run, safe_form_state

router = APIRouter()

RUNNERS: dict[str, Callable[..., None]] = {
    "vcenter": vcenter._run_vcenter_connector_job,
    "prometheus": prometheus._run_prometheus_connector_job,
    "elasticsearch": elasticsearch._run_elasticsearch_connector_job,
    "cassandra": cassandra._run_cassandra_connector_job,
    "ceph": ceph._run_ceph_connector_job,
    "kubernetes": kubernetes._run_kubernetes_connector_job,
}


@router.get("/api/ui/connectors")
def connectors_bootstrap(user=Depends(get_current_ui_user)) -> dict[str, object]:
    return {
        "connectors": [
            {
                "name": name,
                **CONNECTOR_SCHEMAS[name],
                "run_url": f"/api/ui/connectors/{name}/run",
            }
            for name in CONNECTOR_NAMES
        ],
        "asset_types": list(ASSET_TYPES),
        "policy": {
            "can_dry_run": True,
            "can_apply": user.role == UserRole.EDITOR,
            "apply_message": "Editor role is required to apply connector imports.",
        },
        "jobs_url": "/api/ui/connectors/jobs/{job_id}",
        "poll_interval_ms": 1000,
    }


@router.post("/api/ui/connectors/{connector}/run", status_code=status.HTTP_202_ACCEPTED)
async def run_connector_api(
    connector: str,
    request: Request,
    background_tasks: BackgroundTasks,
    db_path: str = Depends(get_db_path),
    user=Depends(get_current_ui_user),
) -> dict[str, object]:
    if connector not in RUNNERS:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown connector.")
    try:
        raw_payload = await request.json()
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Request body must be valid JSON.") from exc
    if not isinstance(raw_payload, dict):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Request body must be a JSON object.")
    parsed, errors = parse_connector_run(connector, raw_payload)
    if errors or parsed is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=errors)
    if parsed.mode == "apply" and user.role != UserRole.EDITOR:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Apply mode is restricted to editor accounts.")

    job_id = _create_connector_job(active_tab=connector, form_state=parsed.form_state)
    background_tasks.add_task(
        RUNNERS[connector],
        job_id=job_id,
        db_path=db_path,
        user_id=int(user.id),
        **parsed.task_kwargs,
    )
    return {
        "job_id": job_id,
        "connector": connector,
        "status": "queued",
        "poll_url": f"/api/ui/connectors/jobs/{job_id}",
    }


@router.get("/api/ui/connectors/jobs/{job_id}")
def connector_job_api(
    job_id: str,
    _user=Depends(get_current_ui_user),
) -> dict[str, Any]:
    job = _get_connector_job(job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connector job was not found or has expired.")
    job_status = str(job.get("status") or "queued")
    connector = str(job.get("connector") or job.get("active_tab") or "")
    return {
        "job_id": job_id,
        "connector": connector,
        "active_tab": connector,
        "status": job_status,
        "form_state": safe_form_state(dict(job.get("form_state") or {})),
        "logs": [str(line) for line in job.get("logs") or []],
        "toast_messages": list(job.get("toast_messages") or []),
        "polling": job_status in {"queued", "running"},
    }
