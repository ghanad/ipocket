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


IANA_ENTERPRISE_MAP: dict[int, str] = {
    674: "Dell",
    232: "HPE",
    10876: "Supermicro",
    47692: "Supermicro",
    20301: "Lenovo",
    2011: "Huawei",
    9: "Cisco",
    7244: "Quanta",
    311: "Microsoft",
}


def _build_permissive_ssl_context(
    ciphers: str = "ALL:!aNULL:!eNULL:@SECLEVEL=0",
) -> ssl.SSLContext:
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    try:
        import warnings

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            ctx.minimum_version = ssl.TLSVersion.TLSv1
    except (AttributeError, ValueError):
        pass
    for cipher_spec in [ciphers, "DEFAULT:@SECLEVEL=0", "ALL:!aNULL"]:
        try:
            ctx.set_ciphers(cipher_spec)
            break
        except ssl.SSLError:
            continue
    return ctx


def probe_bmc_rmcp(ip: str, port: int = 623, timeout: float = 1.0) -> Optional[dict[str, Any]]:
    """Sends an ASF Presence Ping on UDP port 623 and extracts IANA Enterprise ID."""
    asf_ping = b"\x06\x00\xff\x07\x00\x00\x11\xbe\x80\x01\x00\x00"
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(timeout)
    try:
        sock.sendto(asf_ping, (ip, port))
        data, _ = sock.recvfrom(512)
        if len(data) >= 16 and data[8:9] == b"\x40":
            iana_id = int.from_bytes(data[12:16], "big")
            vendor = IANA_ENTERPRISE_MAP.get(iana_id)
            if not vendor and len(data) >= 20:
                iana_id = int.from_bytes(data[16:20], "big")
                vendor = IANA_ENTERPRISE_MAP.get(iana_id)
            if vendor:
                return {
                    "status": "matched",
                    "detected_vendor": vendor,
                    "confidence": "high",
                    "fingerprint_summary": f"IPMI RMCP (UDP 623) Enterprise ID {iana_id} ({vendor})",
                    "error": None,
                }
    except Exception:
        pass
    finally:
        sock.close()
    return None


def probe_bmc_http(ip: str, port: int = 80, timeout: float = 1.5) -> Optional[dict[str, Any]]:
    """Probes port 80 for HTTP Server headers, redirects, or HTML titles."""
    try:
        with socket.create_connection((ip, port), timeout=timeout) as sock:
            sock.settimeout(timeout)
            req = f"GET / HTTP/1.1\r\nHost: {ip}\r\nUser-Agent: ipocket-scanner/1.0\r\nConnection: close\r\n\r\n".encode("ascii")
            sock.sendall(req)
            resp_bytes = sock.recv(4096)
            text = resp_bytes.decode("latin1", errors="ignore")
            vendor = normalize_vendor(text)
            if vendor:
                lines = text.splitlines()
                evidence = next(
                    (line.strip() for line in lines if normalize_vendor(line) == vendor),
                    text[:100].strip(),
                )
                return {
                    "status": "matched",
                    "detected_vendor": vendor,
                    "confidence": "high",
                    "fingerprint_summary": f"HTTP port 80: {evidence[:100]}",
                    "error": None,
                }
    except Exception:
        pass
    return None


def _attempt_tls(
    ip: str,
    port: int,
    timeout: float,
    ciphers: str,
    server_hostname: Optional[str],
) -> tuple[Optional[list[str]], Optional[str], Optional[str]]:
    """Attempts TLS connection. Returns (evidence_strings, error_kind, raw_error_message)."""
    ctx = _build_permissive_ssl_context(ciphers)
    try:
        with socket.create_connection((ip, port), timeout=timeout) as sock:
            with ctx.wrap_socket(sock, server_hostname=server_hostname) as ssock:
                der_cert = ssock.getpeercert(binary_form=True)
                if der_cert:
                    return extract_der_strings(der_cert), None, None
                return [], None, None
    except socket.timeout:
        return None, "timeout", "Timeout connecting to port 443"
    except ConnectionRefusedError:
        return None, "refused", "Port 443 connection refused"
    except ssl.SSLError as exc:
        err = str(exc).lower()
        if "dh_key_too_small" in err or "dh key too small" in err:
            return None, "dh_key_too_small", str(exc)
        if "handshake_failure" in err or "alert" in err:
            return None, "handshake_failure", str(exc)
        return None, "ssl_error", str(exc)
    except Exception as exc:
        return None, "error", str(exc)


def probe_bmc_tls(ip: str, port: int = 443, timeout: float = 2.0) -> dict[str, Any]:
    """Probes a BMC IP over SSL/TLS port 443 with fallback to HTTP and RMCP.

    Gracefully handles legacy BMC firmware issues like:
    - dh_key_too_small (disables DHE or lowers SECLEVEL to 0)
    - sslv3_alert_handshake_failure (allows TLS 1.0/1.1 and handles SNI)
    - Port 443 timeout / closed (falls back to port 80 HTTP and port 623 RMCP)
    """
    evidence_parts: list[str] = []
    last_error_kind: Optional[str] = None
    last_raw_error: Optional[str] = None

    # Step 1: Attempt TLS without SNI and permissive ciphers (@SECLEVEL=0)
    strings, err_kind, raw_err = _attempt_tls(
        ip, port, timeout, "ALL:!aNULL:!eNULL:@SECLEVEL=0", server_hostname=None
    )

    # Step 2: Handle dh_key_too_small by retrying with DHE ciphers disabled
    if err_kind == "dh_key_too_small":
        strings, err_kind, raw_err = _attempt_tls(
            ip, port, timeout, "DEFAULT:!DH:!DHE:@SECLEVEL=0", server_hostname=None
        )

    # Step 3: Handle handshake_failure by trying with SNI
    if err_kind == "handshake_failure":
        strings, err_kind, raw_err = _attempt_tls(
            ip, port, timeout, "ALL:!aNULL:!eNULL:@SECLEVEL=0", server_hostname=ip
        )

    if strings is not None:
        evidence_parts.extend(strings)
        joined_evidence = " | ".join(evidence_parts)
        vendor = normalize_vendor(joined_evidence)
        if vendor:
            relevant = [s for s in evidence_parts if normalize_vendor(s) == vendor]
            summary = ", ".join(relevant[:3]) if relevant else joined_evidence[:120]
            return {
                "status": "matched",
                "detected_vendor": vendor,
                "confidence": "high",
                "fingerprint_summary": summary,
                "error": None,
            }
    else:
        last_error_kind = err_kind
        last_raw_error = raw_err

    # Step 4: Fallback to Port 80 HTTP banner
    http_result = probe_bmc_http(ip, port=80, timeout=min(timeout, 1.5))
    if http_result and http_result.get("detected_vendor"):
        return http_result

    # Step 5: Fallback to UDP 623 IPMI RMCP Presence Ping
    rmcp_result = probe_bmc_rmcp(ip, port=623, timeout=min(timeout, 1.0))
    if rmcp_result and rmcp_result.get("detected_vendor"):
        return rmcp_result

    # If all probes failed or didn't produce a vendor
    if last_error_kind == "timeout":
        return {
            "status": "timeout",
            "detected_vendor": None,
            "confidence": None,
            "fingerprint_summary": "Connection timed out",
            "error": "Timeout connecting to port 443",
        }
    if last_error_kind == "refused":
        return {
            "status": "unmatched",
            "detected_vendor": None,
            "confidence": None,
            "fingerprint_summary": "Port 443 connection refused",
            "error": "Connection refused",
        }
    if last_raw_error:
        return {
            "status": "error",
            "detected_vendor": None,
            "confidence": None,
            "fingerprint_summary": f"TLS error: {last_raw_error[:100]}",
            "error": last_raw_error,
        }

    joined_evidence = " | ".join(evidence_parts)
    return {
        "status": "unmatched",
        "detected_vendor": None,
        "confidence": None,
        "fingerprint_summary": joined_evidence[:120]
        if joined_evidence
        else "No certificate or banner strings found",
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
