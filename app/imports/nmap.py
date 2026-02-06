from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import ipaddress
from typing import Optional
import xml.etree.ElementTree as ET

from app import repository
from app.models import IPAssetType, User


class NmapParseError(Exception):
    pass


@dataclass
class NmapParseResult:
    ip_addresses: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


@dataclass
class NmapImportAsset:
    id: int
    ip_address: str


@dataclass
class NmapImportResult:
    discovered_up_hosts: int
    new_ips_created: int
    existing_ips_seen: int
    errors: list[str] = field(default_factory=list)
    new_assets: list[NmapImportAsset] = field(default_factory=list)


def parse_nmap_xml(payload: bytes) -> NmapParseResult:
    try:
        root = ET.fromstring(payload)
    except ET.ParseError as exc:
        raise NmapParseError("Invalid Nmap XML payload.") from exc

    ip_addresses: list[str] = []
    errors: list[str] = []

    for host in root.findall("host"):
        status = host.find("status")
        if status is None or status.get("state") != "up":
            continue
        ipv4_address = None
        for address in host.findall("address"):
            if address.get("addrtype") == "ipv4":
                ipv4_address = address.get("addr")
                break
        if not ipv4_address:
            continue
        try:
            parsed_ip = ipaddress.ip_address(ipv4_address)
        except ValueError:
            errors.append(f"Invalid IP address '{ipv4_address}' in Nmap XML.")
            continue
        if parsed_ip.version != 4:
            continue
        ip_addresses.append(str(parsed_ip))

    return NmapParseResult(ip_addresses=ip_addresses, errors=errors)


def _unique_ip_addresses(ip_addresses: list[str]) -> list[str]:
    unique: list[str] = []
    seen: set[str] = set()
    for ip_address in ip_addresses:
        if ip_address in seen:
            continue
        seen.add(ip_address)
        unique.append(ip_address)
    return unique


def import_nmap_xml(
    connection,
    payload: bytes,
    *,
    dry_run: bool = False,
    current_user: Optional[User] = None,
    now: Optional[datetime] = None,
) -> NmapImportResult:
    try:
        parse_result = parse_nmap_xml(payload)
    except NmapParseError as exc:
        return NmapImportResult(
            discovered_up_hosts=0,
            new_ips_created=0,
            existing_ips_seen=0,
            errors=[str(exc)],
        )

    unique_ips = _unique_ip_addresses(parse_result.ip_addresses)
    timestamp = (now or datetime.now(timezone.utc)).isoformat(timespec="seconds")
    note = f"Discovered via nmap upload at {timestamp}"

    new_assets: list[NmapImportAsset] = []
    new_ips_created = 0
    existing_ips_seen = 0

    for ip_address in unique_ips:
        existing = repository.get_ip_asset_by_ip(connection, ip_address)
        if existing is not None:
            existing_ips_seen += 1
            continue
        new_ips_created += 1
        if dry_run:
            continue
        asset = repository.create_ip_asset(
            connection,
            ip_address=ip_address,
            asset_type=IPAssetType.OTHER,
            notes=note,
            current_user=current_user,
        )
        new_assets.append(NmapImportAsset(id=asset.id, ip_address=asset.ip_address))

    return NmapImportResult(
        discovered_up_hosts=len(unique_ips),
        new_ips_created=new_ips_created,
        existing_ips_seen=existing_ips_seen,
        errors=parse_result.errors,
        new_assets=new_assets,
    )
