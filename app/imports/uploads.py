from __future__ import annotations

from typing import Protocol

IMPORT_UPLOAD_CHUNK_SIZE = 64 * 1024
IMPORT_UPLOAD_MAX_BYTES = 10 * 1024 * 1024


class UploadTooLargeError(ValueError):
    """Raised when an uploaded file exceeds the configured size limit."""


class UploadLike(Protocol):
    async def read(self, size: int = -1) -> bytes: ...


async def read_upload_limited(
    upload: UploadLike,
    *,
    max_bytes: int = IMPORT_UPLOAD_MAX_BYTES,
    chunk_size: int = IMPORT_UPLOAD_CHUNK_SIZE,
) -> bytes:
    if max_bytes < 0:
        raise ValueError("max_bytes must be non-negative")
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")

    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await upload.read(chunk_size)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise UploadTooLargeError
        chunks.append(chunk)

    return b"".join(chunks)


def describe_upload_limit(max_bytes: int) -> str:
    mb = 1024 * 1024
    if max_bytes % mb == 0 and max_bytes >= mb:
        return f"{max_bytes // mb} MB"
    if max_bytes == 1:
        return "1 byte"
    return f"{max_bytes} bytes"
