from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from app import repository
from app.imports.applier import apply_bundle
from app.imports.importers import Importer
from app.imports.models import (
    ImportApplyResult,
    ImportIssue,
    ImportParseError,
    ImportSummary,
)
from app.imports.validator import validate_bundle


@dataclass
class ImportAuditContext:
    user: object | None
    source: str
    mode: str
    input_label: str


def _record_import_apply_audit(
    connection,
    *,
    context: ImportAuditContext,
    result: ImportApplyResult,
) -> None:
    total = result.summary.total()
    changes = (
        f"Import apply source={context.source}; input={context.input_label}; "
        f"create={total.would_create}; update={total.would_update}; "
        f"skip={total.would_skip}; warnings={len(result.warnings)}; "
        f"errors={len(result.errors)}."
    )
    with connection:
        repository.create_audit_log(
            connection,
            user=context.user,
            action="APPLY",
            target_type="IMPORT_RUN",
            target_id=0,
            target_label=context.source,
            changes=changes,
        )


def run_import(
    connection,
    importer: Importer,
    inputs: dict[str, bytes],
    *,
    options: Optional[dict[str, object]] = None,
    dry_run: bool = False,
    audit_context: Optional[ImportAuditContext] = None,
) -> ImportApplyResult:
    try:
        bundle = importer.parse(inputs, options=options)
    except ImportParseError as exc:
        return ImportApplyResult(
            summary=ImportSummary(),
            errors=[ImportIssue(location=exc.location, message=str(exc))],
        )

    validation = validate_bundle(connection, bundle)
    if not validation.is_valid:
        return ImportApplyResult(
            summary=ImportSummary(),
            errors=validation.errors,
            warnings=validation.warnings,
        )

    applied = apply_bundle(connection, bundle, dry_run=dry_run)
    applied.warnings = validation.warnings + applied.warnings
    if (
        not dry_run
        and audit_context is not None
        and audit_context.mode.lower() == "apply"
        and not applied.errors
    ):
        _record_import_apply_audit(
            connection,
            context=audit_context,
            result=applied,
        )
    return applied
