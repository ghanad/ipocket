from __future__ import annotations


def _finalize_job_logs(
    *,
    logs: list[str],
    warnings: list[str],
    import_warning_count: int,
    import_error_count: int,
) -> tuple[list[str], list[dict[str, str]]]:
    final_logs = [*logs]
    if warnings:
        final_logs.append(f"Connector warnings: {len(warnings)}")
        for warning in warnings:
            final_logs.append(f"- {warning}")

    toast_messages: list[dict[str, str]] = []
    if import_error_count > 0:
        toast_messages.append(
            {
                "type": "error",
                "message": f"Connector completed with {import_error_count} import error(s).",
            }
        )
    elif import_warning_count > 0 or warnings:
        toast_messages.append(
            {
                "type": "warning",
                "message": "Connector completed with warnings. Review execution log.",
            }
        )
    else:
        toast_messages.append(
            {
                "type": "success",
                "message": "Connector completed successfully.",
            }
        )
    return final_logs, toast_messages
