from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class ImportSource:
    location: str


@dataclass
class ImportVendor:
    name: str
    source: Optional[ImportSource] = None


@dataclass
class ImportProject:
    name: str
    description: Optional[str] = None
    color: Optional[str] = None
    source: Optional[ImportSource] = None


@dataclass
class ImportHost:
    name: str
    notes: Optional[str] = None
    vendor_name: Optional[str] = None
    source: Optional[ImportSource] = None


@dataclass
class ImportIPAsset:
    ip_address: str
    asset_type: str
    project_name: Optional[str] = None
    host_name: Optional[str] = None
    notes: Optional[str] = None
    archived: Optional[bool] = None
    source: Optional[ImportSource] = None


@dataclass
class ImportBundle:
    vendors: list[ImportVendor] = field(default_factory=list)
    projects: list[ImportProject] = field(default_factory=list)
    hosts: list[ImportHost] = field(default_factory=list)
    ip_assets: list[ImportIPAsset] = field(default_factory=list)


@dataclass
class ImportIssue:
    location: str
    message: str
    level: str = "error"


@dataclass
class ImportValidationResult:
    errors: list[ImportIssue] = field(default_factory=list)
    warnings: list[ImportIssue] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return not self.errors


@dataclass
class ImportEntitySummary:
    would_create: int = 0
    would_update: int = 0
    would_skip: int = 0


@dataclass
class ImportSummary:
    vendors: ImportEntitySummary = field(default_factory=ImportEntitySummary)
    projects: ImportEntitySummary = field(default_factory=ImportEntitySummary)
    hosts: ImportEntitySummary = field(default_factory=ImportEntitySummary)
    ip_assets: ImportEntitySummary = field(default_factory=ImportEntitySummary)

    def total(self) -> ImportEntitySummary:
        return ImportEntitySummary(
            would_create=self.vendors.would_create
            + self.projects.would_create
            + self.hosts.would_create
            + self.ip_assets.would_create,
            would_update=self.vendors.would_update
            + self.projects.would_update
            + self.hosts.would_update
            + self.ip_assets.would_update,
            would_skip=self.vendors.would_skip
            + self.projects.would_skip
            + self.hosts.would_skip
            + self.ip_assets.would_skip,
        )


@dataclass
class ImportApplyResult:
    summary: ImportSummary
    errors: list[ImportIssue] = field(default_factory=list)
    warnings: list[ImportIssue] = field(default_factory=list)


class ImportParseError(Exception):
    def __init__(self, message: str, location: str = "import") -> None:
        super().__init__(message)
        self.location = location
