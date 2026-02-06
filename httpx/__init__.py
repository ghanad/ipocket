from __future__ import annotations

import json
from typing import Any, Iterable, Mapping, Optional
from urllib.parse import urlencode, urljoin, urlsplit

from . import _client, _types


class BaseTransport:
    def handle_request(self, request: "Request") -> "Response":
        raise NotImplementedError


class ByteStream:
    def __init__(self, content: bytes) -> None:
        self._content = content

    def read(self) -> bytes:
        return self._content


class Headers:
    def __init__(self, headers: Optional[Mapping[str, str]] = None) -> None:
        self._items: list[tuple[str, str]] = []
        if headers:
            for key, value in headers.items():
                self._items.append((key, value))

    def multi_items(self) -> list[tuple[str, str]]:
        return list(self._items)

    def get(self, key: str, default: Optional[str] = None) -> Optional[str]:
        for item_key, value in self._items:
            if item_key.lower() == key.lower():
                return value
        return default

    def __contains__(self, key: str) -> bool:
        return self.get(key) is not None


class URL:
    def __init__(self, url: str) -> None:
        parts = urlsplit(url)
        self.scheme = parts.scheme or "http"
        netloc = parts.netloc
        if not netloc and parts.scheme:
            netloc = parts.path
        self.netloc = netloc.encode("ascii")
        self.path = parts.path or "/"
        self.raw_path = self.path.encode("ascii")
        self.query = parts.query.encode("ascii")

    def __str__(self) -> str:
        netloc = self.netloc.decode("ascii")
        query = self.query.decode("ascii")
        if query:
            return f"{self.scheme}://{netloc}{self.path}?{query}"
        return f"{self.scheme}://{netloc}{self.path}"


class Request:
    def __init__(
        self,
        method: str,
        url: URL,
        headers: Optional[Mapping[str, str]] = None,
        content: Optional[bytes] = None,
    ) -> None:
        self.method = method.upper()
        self.url = url
        self.headers = Headers(headers)
        self._content = content or b""

    def read(self) -> bytes:
        return self._content


class ResponseHeaders:
    def __init__(self, headers: Iterable[tuple[str, str]]) -> None:
        self._headers = {key.lower(): value for key, value in headers}

    def __getitem__(self, key: str) -> str:
        return self._headers[key.lower()]

    def get(self, key: str, default: Optional[str] = None) -> Optional[str]:
        return self._headers.get(key.lower(), default)

    def items(self):
        return self._headers.items()

    def __contains__(self, key: str) -> bool:
        return key.lower() in self._headers


class Response:
    def __init__(
        self,
        status_code: int,
        headers: Iterable[tuple[str, str]] | None = None,
        stream: ByteStream | None = None,
        request: Request | None = None,
    ) -> None:
        self.status_code = status_code
        self.headers = ResponseHeaders(headers or [])
        self._content = stream.read() if stream else b""
        self.request = request

    @property
    def text(self) -> str:
        return self._content.decode("utf-8")

    def json(self) -> Any:
        return json.loads(self._content.decode("utf-8"))


class Client:
    def __init__(
        self,
        base_url: str = "http://testserver",
        headers: Optional[Mapping[str, str]] = None,
        transport: Optional[BaseTransport] = None,
        follow_redirects: bool = True,
        cookies: Optional[Mapping[str, str]] = None,
    ) -> None:
        self.base_url = base_url
        self.headers = headers or {}
        self.transport = transport or BaseTransport()
        self.follow_redirects = follow_redirects
        self.cookies = cookies or {}

    def _merge_url(self, url: _types.URLTypes) -> URL:
        if isinstance(url, URL):
            return url
        if "://" in url:
            return URL(url)
        return URL(urljoin(self.base_url, url))

    def request(
        self,
        method: str,
        url: _types.URLTypes,
        *,
        content: _types.RequestContent | None = None,
        data: Mapping[str, Any] | None = None,
        files: _types.RequestFiles | None = None,
        json: Any = None,
        params: _types.QueryParamTypes | None = None,
        headers: _types.HeaderTypes | None = None,
        cookies: _types.CookieTypes | None = None,
        auth: _types.AuthTypes | _client.UseClientDefault = _client.USE_CLIENT_DEFAULT,
        follow_redirects: bool | None = None,
        timeout: _types.TimeoutTypes | _client.UseClientDefault = _client.USE_CLIENT_DEFAULT,
        extensions: Mapping[str, Any] | None = None,
    ) -> Response:
        merged_url = self._merge_url(url)
        if params:
            query = urlencode(params, doseq=True)
            merged_url = URL(f"{str(merged_url)}?{query}")
        request_headers = dict(self.headers)
        if headers:
            request_headers.update(headers)
        body: Optional[bytes] = None
        if json is not None:
            body = json_encode(json)
            request_headers.setdefault("content-type", "application/json")
        elif files is not None:
            boundary = "----ipocketformboundary"
            parts: list[bytes] = []
            if data:
                for key, value in data.items():
                    parts.append(
                        b"".join(
                            [
                                f"--{boundary}\r\n".encode("utf-8"),
                                f'Content-Disposition: form-data; name="{key}"\r\n\r\n'.encode(
                                    "utf-8"
                                ),
                                _to_bytes(value),
                                b"\r\n",
                            ]
                        )
                    )
            for field, file_info in _iter_files(files):
                filename, file_content, content_type = file_info
                parts.append(
                    b"".join(
                        [
                            f"--{boundary}\r\n".encode("utf-8"),
                            f'Content-Disposition: form-data; name="{field}"; filename="{filename}"\r\n'.encode(
                                "utf-8"
                            ),
                            f"Content-Type: {content_type}\r\n\r\n".encode("utf-8"),
                            _to_bytes(file_content),
                            b"\r\n",
                        ]
                    )
                )
            parts.append(f"--{boundary}--\r\n".encode("utf-8"))
            body = b"".join(parts)
            request_headers.setdefault("content-type", f"multipart/form-data; boundary={boundary}")
        elif content is not None:
            body = content.encode("utf-8") if isinstance(content, str) else content
        elif data is not None:
            body = urlencode(data, doseq=True).encode("utf-8")
            request_headers.setdefault("content-type", "application/x-www-form-urlencoded")
        request = Request(method, merged_url, headers=request_headers, content=body)
        return self.transport.handle_request(request)

    def get(self, url: _types.URLTypes, **kwargs: Any) -> Response:
        return self.request("GET", url, **kwargs)

    def post(self, url: _types.URLTypes, **kwargs: Any) -> Response:
        return self.request("POST", url, **kwargs)

    def patch(self, url: _types.URLTypes, **kwargs: Any) -> Response:
        return self.request("PATCH", url, **kwargs)


def json_encode(value: Any) -> bytes:
    return json.dumps(value, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _to_bytes(value: Any) -> bytes:
    if value is None:
        return b""
    if isinstance(value, bytes):
        return value
    if hasattr(value, "read"):
        return value.read()
    return str(value).encode("utf-8")


def _iter_files(files: _types.RequestFiles) -> list[tuple[str, tuple[str, Any, str]]]:
    items = files.items() if isinstance(files, Mapping) else files
    normalized: list[tuple[str, tuple[str, Any, str]]] = []
    for field, file_value in items:
        filename = "upload"
        content = file_value
        content_type = "application/octet-stream"
        if isinstance(file_value, tuple):
            if len(file_value) == 3:
                filename, content, content_type = file_value
            elif len(file_value) == 2:
                filename, content = file_value
        else:
            filename = getattr(file_value, "name", filename)
        normalized.append((field, (str(filename), content, str(content_type))))
    return normalized


__all__ = [
    "BaseTransport",
    "ByteStream",
    "Client",
    "Headers",
    "Request",
    "Response",
    "URL",
    "_client",
    "_types",
]
