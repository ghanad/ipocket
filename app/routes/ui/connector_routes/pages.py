from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Query, Request
from fastapi.responses import HTMLResponse

from app.routes.ui.utils import _render_template
from .forms import (
    _connectors_context,
    _default_cassandra_form_state,
    _default_ceph_form_state,
    _default_elasticsearch_form_state,
    _default_kubernetes_form_state,
    _default_prometheus_form_state,
    _default_vcenter_form_state,
)
from .job_store import _get_connector_job

router = APIRouter()


@router.get("/ui/connectors", response_class=HTMLResponse)
def ui_connectors(
    request: Request,
    tab: Optional[str] = Query(default=None),
    job_id: Optional[str] = Query(default=None),
) -> HTMLResponse:
    active_tab = (
        tab
        if tab
        in {
            "overview",
            "vcenter",
            "prometheus",
            "elasticsearch",
            "cassandra",
            "ceph",
            "kubernetes",
        }
        else "overview"
    )
    context = _connectors_context(active_tab=active_tab)
    if job_id:
        job = _get_connector_job(job_id)
        if job is not None:
            active_tab = str(job.get("active_tab") or active_tab)
            context["active_tab"] = active_tab
            status_value = str(job.get("status") or "queued")
            logs = list(job.get("logs") or [])
            toast_messages = list(job.get("toast_messages") or [])
            form_state = dict(job.get("form_state") or {})
            if active_tab == "vcenter":
                context["vcenter_form_state"] = (
                    form_state or _default_vcenter_form_state()
                )
                context["vcenter_logs"] = logs
            elif active_tab == "prometheus":
                context["prometheus_form_state"] = (
                    form_state or _default_prometheus_form_state()
                )
                context["prometheus_logs"] = logs
            elif active_tab == "elasticsearch":
                context["elasticsearch_form_state"] = (
                    form_state or _default_elasticsearch_form_state()
                )
                context["elasticsearch_logs"] = logs
            elif active_tab == "cassandra":
                context["cassandra_form_state"] = (
                    form_state or _default_cassandra_form_state()
                )
                context["cassandra_logs"] = logs
            elif active_tab == "ceph":
                context["ceph_form_state"] = form_state or _default_ceph_form_state()
                context["ceph_logs"] = logs
            elif active_tab == "kubernetes":
                context["kubernetes_form_state"] = (
                    form_state or _default_kubernetes_form_state()
                )
                context["kubernetes_logs"] = logs
            if status_value in {"queued", "running"}:
                context["connector_job_poll_url"] = (
                    f"/ui/connectors?tab={active_tab}&job_id={job_id}"
                )
                context["toast_messages"] = [
                    {
                        "type": "warning",
                        "message": f"{active_tab} connector run is still in progress.",
                    }
                ]
            else:
                context["toast_messages"] = toast_messages
    return _render_template(
        request,
        "connectors.html",
        context,
        active_nav="connectors",
    )
