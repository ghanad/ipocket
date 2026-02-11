from __future__ import annotations

from typing import TYPE_CHECKING, Any, Mapping, Union

from ._client import UseClientDefault

if TYPE_CHECKING:
    from . import URL

URLTypes = Union[str, "URL"]
QueryParamTypes = Mapping[str, Any]
HeaderTypes = Mapping[str, str]
CookieTypes = Mapping[str, str]
RequestContent = Union[str, bytes]
RequestFiles = Any
AuthTypes = Any
TimeoutTypes = Any

UseClientDefaultType = UseClientDefault
