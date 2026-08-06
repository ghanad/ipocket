# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Infrastructure and operations teams use ipocket to inventory IP assets, connect
them to Hosts and Projects, review assignment gaps, and expose inventory data to
monitoring and automation systems.

## Product Purpose

ipocket provides a lightweight, modular source of truth for IP inventory. It
helps operators keep address, Host, Project, Vendor, Tag, and range data usable
while making incomplete assignments and Host relationships visible.

## Positioning

The product combines direct inventory workflows with connector-driven ingestion,
Prometheus metrics, service discovery, and read-only Host Completion analysis in
one intentionally small application.

## Operating Context

Operators work primarily through the React web UI and use JSON endpoints for
automation. The IP Assets list is the main project-assignment workflow. Host
Completion analytics is a read-only diagnostic view over active Host/IP asset
relationships and refreshes while operators monitor inventory health.

## Capabilities and Constraints

- IP assets support CRUD, archive, filtering, imports, exports, and connector
  ingestion.
- Hosts group active OS, BMC, and other IP assets.
- Host Completion exposes cases, examples, and analytics without database writes.
- Prometheus metrics and HTTP service discovery are stable operational contracts.
- Owner support is paused and retained only where compatibility requires it.
- Feature changes require unit tests and practical documentation under `/docs`.

## Evidence on Hand

The repository contains the production interface, API contracts, tests, and
operational documentation. No customer claims, benchmarks, or external brand
assets are established.

## Product Principles

- Keep operational state easy to scan and verify.
- Prefer low-click workflows and stable read contracts.
- Preserve clean repository, service, and HTTP boundaries.
- Make incomplete inventory visible without mutating it implicitly.
- Keep the application lightweight and modular.

## Accessibility & Inclusion

The web interface should preserve semantic controls, keyboard access, readable
contrast, reduced-motion preferences, and non-visual equivalents for charts.
