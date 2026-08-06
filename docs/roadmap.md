# Roadmap

The current product already includes IP inventory CRUD, project assignment,
Hosts/Vendors/Tags/Ranges, import/export, audit logs, service discovery,
Prometheus metrics, React UI, and connector-driven ingestion.

## Candidate next work

- Scheduled or operator-triggered health checks for selected addresses/services.
- Range discovery with explicit NEW/GONE review instead of automatic mutation.
- Host Completion suggestions and human feedback, building on the existing
  read-only cases/examples/analytics API.

Host Completion is a design proposal rather than a committed release plan. See
[Host Completion Agents](host-completion-agents.md) and the implemented read-only
[Host Completion API](host-completion-api.md).
