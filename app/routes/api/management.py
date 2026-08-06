from __future__ import annotations

from fastapi import APIRouter, Depends

from app import repository
from app.dependencies import get_connection

router = APIRouter()


@router.get("/api/management/overview")
def management_overview(connection=Depends(get_connection)):
    utilization = repository.get_ip_range_utilization(connection)
    return {
        "summary": repository.get_management_summary(connection),
        "utilization": [
            {
                "id": row["id"],
                "name": row["name"],
                "cidr": row["cidr"],
                "total_usable": row["total_usable"],
                "used": row["used"],
                "free": row["free"],
                "utilization_percent": row["utilization_percent"],
            }
            for row in utilization
        ],
    }
