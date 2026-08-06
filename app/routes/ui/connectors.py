from __future__ import annotations

from fastapi import APIRouter

from .connector_routes import (
    api,
    cassandra,
    ceph,
    elasticsearch,
    kubernetes,
    pages,
    prometheus,
    vcenter,
)

router = APIRouter()
router.include_router(api.router)
router.include_router(pages.router)
router.include_router(vcenter.router)
router.include_router(prometheus.router)
router.include_router(elasticsearch.router)
router.include_router(cassandra.router)
router.include_router(ceph.router)
router.include_router(kubernetes.router)

__all__ = ["router"]
