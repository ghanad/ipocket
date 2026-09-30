from __future__ import annotations

import asyncio
import re
import socket
import ssl
from typing import Any, Iterable, Optional, Sequence

from sqlalchemy.orm import Session
import sqlite3

from app import repository
from app.models import User
from app.repository.audit import create_audit_log
from app.repository._db import write_session_scope

# Vendor normalization patterns (canonical_name, pattern_list)
VENDOR_PATTERNS: list[tuple[str, list[re.Pattern[str]]]] = [
    (
        "Dell",
        [
            re.compile(r"\bdell\b", re.IGNORECASE),
            re.compile(r"\bidrac\b", re.IGNORECASE),
            re.compile(r"\bpoweredge\b", re.IGNORECASE),
        ],
    ),
    (
        "HPE",
        [
            re.compile(r"\bhewlett[-\s]?packard\b", re.IGNORECASE),
            re.compile(r"\bhpe\b", re.IGNORECASE),
            re.compile(r"\bilo[3-6]?\b", re.IGNORECASE),
            re.compile(r"\bproliant\b", re.IGNORECASE),
        ],
    ),
    (
        "Supermicro",
        [
            re.compile(r"\bsuper\s*micro\b", re.IGNORECASE),
            re.compile(r"\bsupermicro\b", re.IGNORECASE),
            re.compile(r"\bmegarac\b", re.IGNORECASE),
            re.compile(r"\bamerican\s+megatrends\b", re.IGNORECASE),
        ],
    ),
    (
        "Cisco",
        [
            re.compile(r"\bcisco\b", re.IGNORECASE),
            re.compile(r"\bcimc\b", re.IGNORECASE),
            re.compile(r"\bucs\b", re.IGNORECASE),
        ],
    ),
    (
        "Lenovo",
        [
            re.compile(r"\blenovo\b", re.IGNORECASE),
            re.compile(r"\bxclarity\b", re.IGNORECASE),
            re.compile(r"\bimm2\b", re.IGNORECASE),
            re.compile(r"\bthinksystem\b", re.IGNORECASE),
            re.compile(r"\bthinkserver\b", re.IGNORECASE),
        ],
    ),
    (
        "Huawei",
        [
            re.compile(r"\bhuawei\b", re.IGNORECASE),
            re.compile(r"\bibmc\b", re.IGNORECASE),
        ],
    ),
    (
        "Inspur",
        [
            re.compile(r"\binspur\b", re.IGNORECASE),
        ],
    ),
    (
        "Fujitsu",
        [
            re.compile(r"\bfujitsu\b", re.IGNORECASE),
            re.compile(r"\bprimergy\b", re.IGNORECASE),
            re.compile(r"\birmc\b", re.IGNORECASE),
        ],
    ),
    (
        "Quanta",
        [
            re.compile(r"\bquanta\b", re.IGNORECASE),
            re.compile(r"\bqct\b", re.IGNORECASE),
        ],
    ),
]


def normalize_vendor(raw_text: str) -> Optional[str]:
    """Matches text against known vendor signatures and returns canonical vendor name."""
    if not raw_text:
        return None

    for vendor, patterns in VENDOR_PATTERNS:
        for pattern in patterns:
            if pattern.search(raw_text):
                return vendor
    return None


def extract_der_strings(der_bytes: bytes) -> list[str]:
    """Extract human-readable strings from ASN.1 DER certificate bytes."""
    # Find contiguous ASCII printable character chunks of length >= 3
    pattern = re.compile(b"[A-Za-z0-9 ._\\-:=#@,()]{3,}")
    matches = pattern.findall(der_bytes)
    extracted: list[str] = []
    for match in matches:
        text = match.decode("latin1", errors="ignore").strip()
        if text and len(text) >= 3:
            extracted.append(text)
    return extracted


def probe_bmc_tls(ip: str, port: int = 443, timeout: float = 2.0) -> dict[str, Any]:
    """Probes a BMC IP over SSL/TLS port 443 without credentials.

    Returns discovery information including detected vendor and certificate evidence.
    """
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    evidence_parts: list[str] = []
    try:
        with socket.create_connection((ip, port), timeout=timeout) as sock:
            with ctx.wrap_socket(sock, server_hostname=ip) as ssock:
                der_cert = ssock.getpeercert(binary_form=True)
                if der_cert:
                    strings = extract_der_strings(der_cert)
                    evidence_parts.extend(strings)
    except socket.timeout:
        return {
            "status": "timeout",
            "detected_vendor": None,
            "confidence": None,
            "fingerprint_summary": "Connection timed out",
            "error": "Timeout connecting to port 443",
        }
    except ConnectionRefusedError:
        return {
            "status": "unmatched",
            "detected_vendor": None,
            "confidence": None,
            "fingerprint_summary": "Port 443 connection refused",
            "error": "Connection refused",
        }
    except Exception as exc:
        return {
            "status": "error",
            "detected_vendor": None,
            "confidence": None,
            "fingerprint_summary": f"Probe error: {exc}",
            "error": str(exc),
        }

    joined_evidence = " | ".join(evidence_parts)
    vendor = normalize_vendor(joined_evidence)

    if vendor:
        # Build concise summary highlighting why this vendor matched
        relevant = [s for s in evidence_parts if normalize_vendor(s) == vendor]
        summary = ", ".join(relevant[:3]) if relevant else joined_evidence[:120]
        return {
            "status": "matched",
            "detected_vendor": vendor,
            "confidence": "high",
            "fingerprint_summary": summary,
            "error": None,
        }

    return {
        "status": "unmatched",
        "detected_vendor": None,
        "confidence": None,
        "fingerprint_summary": joined_evidence[:120]
        if joined_evidence
        else "No certificate strings found",
        "error": None,
    }


async def scan_bmc_targets(
    targets: Sequence[dict[str, Any]],
    concurrency: int = 20,
    timeout: float = 2.0,
) -> list[dict[str, Any]]:
    """Asynchronously scans targets using bounded concurrency."""
    semaphore = asyncio.Semaphore(concurrency)

    async def scan_target(target: dict[str, Any]) -> dict[str, Any]:
        async with semaphore:
            host_id = int(target["host_id"])
            host_name = str(target["host_name"])
            bmc_assets = target.get("bmc_assets", [])

            if not bmc_assets:
                return {
                    "host_id": host_id,
                    "host_name": host_name,
                    "bmc_ip": None,
                    "detected_vendor": None,
                    "confidence": None,
                    "fingerprint_summary": "No linked BMC IP",
                    "status": "unmatched",
                    "error": "No BMC IP",
                }

            # Probe the first BMC IP (or subsequent if first fails)
            best_result: Optional[dict[str, Any]] = None
            used_ip = ""

            for asset in bmc_assets:
                bmc_ip = asset.get("ip_address")
                if not bmc_ip:
                    continue
                used_ip = bmc_ip
                res = await asyncio.to_thread(probe_bmc_tls, bmc_ip, 443, timeout)
                best_result = res
                if res.get("status") == "matched":
                    break

            if best_result is None:
                return {
                    "host_id": host_id,
                    "host_name": host_name,
                    "bmc_ip": used_ip,
                    "detected_vendor": None,
                    "confidence": None,
                    "fingerprint_summary": "No responsive BMC address",
                    "status": "unmatched",
                    "error": "No responsive BMC IP",
                }

            return {
                "host_id": host_id,
                "host_name": host_name,
                "bmc_ip": used_ip,
                "detected_vendor": best_result.get("detected_vendor"),
                "confidence": best_result.get("confidence"),
                "fingerprint_summary": best_result.get("fingerprint_summary"),
                "status": best_result.get("status", "unmatched"),
                "error": best_result.get("error"),
            }

    tasks = [scan_target(target) for target in targets]
    return await asyncio.gather(*tasks)


def apply_discovered_vendors(
    connection_or_session: sqlite3.Connection | Session,
    items: Iterable[dict[str, Any]],
    current_user: Optional[User] = None,
) -> list[dict[str, Any]]:
    """Applies discovered vendors to target hosts, creating missing vendors and audit logs."""
    applied: list[dict[str, Any]] = []

    with write_session_scope(connection_or_session) as session:
        for item in items:
            host_id = int(item["host_id"])
            vendor_name = str(item["vendor_name"]).strip()
            if not vendor_name:
                continue

            # Ensure vendor exists
            existing_vendor = repository.get_vendor_by_name(session, vendor_name)
            if existing_vendor is None:
                existing_vendor = repository.create_vendor(session, vendor_name)

            updated = repository.update_host(
                session,
                host_id=host_id,
                vendor=vendor_name,
                vendor_provided=True,
            )

            if updated:
                create_audit_log(
                    session,
                    user=current_user,
                    action="UPDATE",
                    target_type="HOST",
                    target_id=host_id,
                    target_label=updated.name,
                    changes=f"Auto-assigned vendor {vendor_name} via BMC SSL discovery.",
                )
                applied.append(
                    {
                        "host_id": host_id,
                        "host_name": updated.name,
                        "vendor_name": vendor_name,
                    }
                )
        session.commit()

    return applied
