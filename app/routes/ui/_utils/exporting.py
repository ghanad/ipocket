from __future__ import annotations

import csv
import io
import zipfile
from urllib.parse import parse_qs

from fastapi import Request
from fastapi.responses import JSONResponse, Response


def _build_csv_content(headers: list[str], rows: list[dict[str, object]]) -> str:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=headers)
    writer.writeheader()
    for row in rows:
        writer.writerow(
            {key: "" if row.get(key) is None else row.get(key) for key in headers}
        )
    return buffer.getvalue()


def _format_ip_asset_csv_rows(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    formatted: list[dict[str, object]] = []
    for row in rows:
        updated = dict(row)
        tags = updated.get("tags")
        if isinstance(tags, list):
            updated["tags"] = ", ".join(tags)
        formatted.append(updated)
    return formatted


def _csv_response(
    filename: str, headers: list[str], rows: list[dict[str, object]]
) -> Response:
    response = Response(
        content=_build_csv_content(headers, rows), media_type="text/csv"
    )
    response.headers["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


def _json_response(filename: str, payload: object) -> Response:
    response = JSONResponse(content=payload)
    response.headers["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


def _zip_response(filename: str, files: dict[str, str]) -> Response:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for file_name, content in files.items():
            archive.writestr(file_name, content)
    response = Response(content=buffer.getvalue(), media_type="application/zip")
    response.headers["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


async def _parse_form_data(request: Request) -> dict:
    body = await request.body()
    parsed = parse_qs(body.decode(), keep_blank_values=True)
    return {key: values[0] for key, values in parsed.items()}


async def _parse_multipart_form(request: Request) -> dict:
    form = await request.form()
    return dict(form)
