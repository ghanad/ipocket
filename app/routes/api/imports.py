from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status

from app.dependencies import get_connection
from app.imports import BundleImporter, CsvImporter, run_import
from app.models import UserRole

from .dependencies import get_current_user
from .utils import import_result_payload

router = APIRouter()


@router.post("/import/bundle")
async def import_bundle_json(
    dry_run: bool = Query(default=False, alias="dry_run"),
    file: UploadFile = File(...),
    connection=Depends(get_connection),
    user=Depends(get_current_user),
):
    if not dry_run and user.role not in (UserRole.EDITOR, UserRole.ADMIN):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
    payload = await file.read()
    result = run_import(
        connection, BundleImporter(), {"bundle": payload}, dry_run=dry_run
    )
    return import_result_payload(result)


@router.post("/import/csv")
async def import_csv_files(
    dry_run: bool = Query(default=False, alias="dry_run"),
    hosts_file: UploadFile | None = File(None, alias="hosts"),
    ip_assets_file: UploadFile | None = File(None, alias="ip_assets"),
    connection=Depends(get_connection),
    user=Depends(get_current_user),
):
    if not dry_run and user.role not in (UserRole.EDITOR, UserRole.ADMIN):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
    if hosts_file is None and ip_assets_file is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="CSV import requires at least one file.",
        )
    inputs: dict[str, bytes] = {}
    if hosts_file is not None:
        hosts_payload = await hosts_file.read()
        if hosts_payload:
            inputs["hosts"] = hosts_payload
    if ip_assets_file is not None:
        ip_assets_payload = await ip_assets_file.read()
        if ip_assets_payload:
            inputs["ip_assets"] = ip_assets_payload
    if not inputs:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="CSV import requires at least one file.",
        )
    result = run_import(connection, CsvImporter(), inputs, dry_run=dry_run)
    return import_result_payload(result)
