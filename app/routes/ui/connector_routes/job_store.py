from __future__ import annotations

import threading
import time
import uuid

from .registry import safe_form_state

_CONNECTOR_JOB_RETENTION_SECONDS = 3600
_CONNECTOR_JOB_LOCK = threading.Lock()
_CONNECTOR_JOBS: dict[str, dict[str, object]] = {}


def _prune_old_connector_jobs(now: float | None = None) -> None:
    current = now or time.time()
    with _CONNECTOR_JOB_LOCK:
        stale_ids = [
            job_id
            for job_id, payload in _CONNECTOR_JOBS.items()
            if current - float(payload.get("updated_at", current))
            > _CONNECTOR_JOB_RETENTION_SECONDS
        ]
        for job_id in stale_ids:
            _CONNECTOR_JOBS.pop(job_id, None)


def _create_connector_job(*, active_tab: str, form_state: dict[str, object]) -> str:
    _prune_old_connector_jobs()
    job_id = uuid.uuid4().hex
    with _CONNECTOR_JOB_LOCK:
        _CONNECTOR_JOBS[job_id] = {
            "active_tab": active_tab,
            "connector": active_tab,
            "form_state": safe_form_state(form_state),
            "status": "queued",
            "logs": [],
            "toast_messages": [],
            "updated_at": time.time(),
        }
    return job_id


def _update_connector_job(job_id: str, **fields: object) -> None:
    if isinstance(fields.get("form_state"), dict):
        fields["form_state"] = safe_form_state(fields["form_state"])  # type: ignore[arg-type]
    with _CONNECTOR_JOB_LOCK:
        existing = _CONNECTOR_JOBS.get(job_id)
        if existing is None:
            return
        existing.update(fields)
        existing["updated_at"] = time.time()


def _get_connector_job(job_id: str) -> dict[str, object] | None:
    _prune_old_connector_jobs()
    with _CONNECTOR_JOB_LOCK:
        payload = _CONNECTOR_JOBS.get(job_id)
        return dict(payload) if payload is not None else None
