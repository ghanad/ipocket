from __future__ import annotations

from typing import Optional

from app.imports.applier import apply_bundle
from app.imports.importers import Importer
from app.imports.models import ImportApplyResult, ImportIssue, ImportParseError, ImportSummary
from app.imports.validator import validate_bundle


def run_import(
    connection,
    importer: Importer,
    inputs: dict[str, bytes],
    *,
    options: Optional[dict[str, object]] = None,
    dry_run: bool = False,
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
        return ImportApplyResult(summary=ImportSummary(), errors=validation.errors, warnings=validation.warnings)

    applied = apply_bundle(connection, bundle, dry_run=dry_run)
    applied.warnings = validation.warnings + applied.warnings
    return applied
