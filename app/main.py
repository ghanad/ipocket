from fastapi import FastAPI, Response

app = FastAPI()


def _metrics_payload() -> str:
    return "\n".join(
        [
            "ipam_ip_total 0",
            "ipam_ip_archived_total 0",
            "ipam_ip_unassigned_owner_total 0",
            "ipam_ip_unassigned_project_total 0",
            "ipam_ip_unassigned_both_total 0",
            "",
        ]
    )


@app.get("/health")
def health_check() -> str:
    return "ok"


@app.get("/metrics")
def metrics() -> Response:
    return Response(content=_metrics_payload(), media_type="text/plain")
