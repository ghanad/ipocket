from __future__ import annotations

from typing import Any, Mapping, Union

from ._client import UseClientDefault

URLTypes = Union[str, "URL"]
QueryParamTypes = Mapping[str, Any]
HeaderTypes = Mapping[str, str]
CookieTypes = Mapping[str, str]
RequestContent = Union[str, bytes]
RequestFiles = Any
AuthTypes = Any
TimeoutTypes = Any

UseClientDefaultType = UseClientDefault
