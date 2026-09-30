from __future__ import annotations

import argparse
import asyncio
import json
import sys
from typing import Sequence

from app import db, repository
from app.dependencies import get_db_path
from app.services import bmc_discovery


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Discover server hardware vendors automatically by probing BMC SSL certificates on port 443."
    )
    parser.add_argument(
        "--host-id",
        type=int,
        action="append",
        dest="host_ids",
        help="Specific host ID to discover (can be specified multiple times).",
    )
    parser.add_argument(
        "--all-hosts",
        action="store_true",
        help="Scan all hosts with BMC addresses, even if they already have a vendor assigned.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=2.0,
        help="Socket timeout in seconds for each TLS probe (default: 2.0).",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=20,
        help="Maximum concurrent network probes (default: 20).",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply discovered vendors to the database.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run discovery and display results without modifying the database (default).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Output results in JSON format.",
    )
    return parser


def run(args: argparse.Namespace) -> int:
    connection = db.connect(get_db_path())
    try:
        targets = repository.get_bmc_discovery_targets(
            connection,
            host_ids=args.host_ids,
            only_unassigned=not args.all_hosts,
        )

        if not targets:
            if args.json_output:
                print(json.dumps({"results": [], "applied": [], "total": 0}))
            else:
                print("No eligible hosts with linked BMC addresses found.")
            return 0

        # Execute async scan
        results = asyncio.run(
            bmc_discovery.scan_bmc_targets(
                targets,
                concurrency=args.concurrency,
                timeout=args.timeout,
            )
        )

        applied: list[dict[str, object]] = []
        if args.apply and not args.dry_run:
            apply_items = [
                {
                    "host_id": r["host_id"],
                    "vendor_name": r["detected_vendor"],
                }
                for r in results
                if r.get("status") == "matched" and r.get("detected_vendor")
            ]
            if apply_items:
                applied = bmc_discovery.apply_discovered_vendors(
                    connection, apply_items
                )

        if args.json_output:
            print(
                json.dumps(
                    {
                        "total": len(results),
                        "matched": sum(
                            1 for r in results if r.get("status") == "matched"
                        ),
                        "results": results,
                        "applied": applied,
                    },
                    indent=2,
                )
            )
            return 0

        # Tabular output
        print(f"\nDiscovered {len(results)} host(s):")
        print(
            f"{'Host ID':<8} {'Host Name':<25} {'BMC IP':<16} {'Vendor':<15} {'Status':<10} {'Evidence'}"
        )
        print("-" * 95)
        for r in results:
            print(
                f"{r['host_id']:<8} "
                f"{str(r['host_name'])[:24]:<25} "
                f"{str(r.get('bmc_ip') or '—'):<16} "
                f"{str(r.get('detected_vendor') or '—'):<15} "
                f"{str(r.get('status')):<10} "
                f"{str(r.get('fingerprint_summary') or '')[:40]}"
            )
        print("-" * 95)

        if args.apply and not args.dry_run:
            print(f"\nApplied vendor changes to {len(applied)} host(s).")
        else:
            matched_count = sum(1 for r in results if r.get("status") == "matched")
            print(
                f"\nDry-run complete. {matched_count} match(es) found. Run with --apply to commit changes."
            )

        return 0
    finally:
        connection.close()


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return run(args)


if __name__ == "__main__":
    sys.exit(main())
