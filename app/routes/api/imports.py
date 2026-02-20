from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status

from app.dependencies import get_connection
from app.imports import BundleImporter, CsvImporter, ImportAuditContext, run_import
from app.imports.uploads import (
    IMPORT_UPLOAD_MAX_BYTES,
    UploadTooLargeError,
    describe_upload_limit,
    read_upload_limited,
)
from app.models import UserRole

from .dependencies import get_current_user
from .utils import import_result_payload

router = APIRouter()


def _upload_size_detail(max_bytes: int) -> str:
    return f"Uploaded file exceeds maximum size of {describe_upload_limit(max_bytes)}."


@router.post("/import/bundle")
async def import_bundle_json(
    dry_run: bool = Query(default=False, alias="dry_run"),
    file: UploadFile = File(...),
    connection=Depends(get_connection),
    user=Depends(get_current_user),
):
    if not dry_run and user.role != UserRole.EDITOR:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
    try:
        payload = await read_upload_limited(file, max_bytes=IMPORT_UPLOAD_MAX_BYTES)
    except UploadTooLargeError as exc:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=_upload_size_detail(IMPORT_UPLOAD_MAX_BYTES),
        ) from exc
    result = run_import(
        connection,
        BundleImporter(),
        {"bundle": payload},
        dry_run=dry_run,
        audit_context=ImportAuditContext(
            user=user,
            source="api_import_bundle",
            mode="apply" if not dry_run else "dry-run",
            input_label="bundle.json",
        ),
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
    if not dry_run and user.role != UserRole.EDITOR:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
    if hosts_file is None and ip_assets_file is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="CSV import requires at least one file.",
        )
    inputs: dict[str, bytes] = {}
    if hosts_file is not None:
        try:
            hosts_payload = await read_upload_limited(
                hosts_file, max_bytes=IMPORT_UPLOAD_MAX_BYTES
            )
        except UploadTooLargeError as exc:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=_upload_size_detail(IMPORT_UPLOAD_MAX_BYTES),
            ) from exc
        if hosts_payload:
            inputs["hosts"] = hosts_payload
    if ip_assets_file is not None:
        try:
            ip_assets_payload = await read_upload_limited(
                ip_assets_file, max_bytes=IMPORT_UPLOAD_MAX_BYTES
            )
        except UploadTooLargeError as exc:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=_upload_size_detail(IMPORT_UPLOAD_MAX_BYTES),
            ) from exc
        if ip_assets_payload:
            inputs["ip_assets"] = ip_assets_payload
    if not inputs:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="CSV import requires at least one file.",
        )
    result = run_import(
        connection,
        CsvImporter(),
        inputs,
        dry_run=dry_run,
        audit_context=ImportAuditContext(
            user=user,
            source="api_import_csv",
            mode="apply" if not dry_run else "dry-run",
            input_label="csv",
        ),
    )
    return import_result_payload(result)
