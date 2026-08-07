# Deterministic ipocket agent

`ipocket_agent` is the isolated, read-only reconciliation component used by
Host Completion. It accepts small `Inventory`, `Host`, `Asset`, and
`AgentDecision` values and returns discovered rules, findings, asset states,
and KPIs. It has no dependency on FastAPI, SQLAlchemy, ipocket repositories,
or the SQLite database.

ipocket remains authoritative for Hosts, IP Assets, Projects, Tags, Ranges,
Users, and Audit Logs. Its adapter builds the current snapshot, serializes the
agent result through authenticated APIs, and owns all transaction-safe writes.

Rules are discovered from confirmed Host relationships. The current rule set
supports `/16` and `/24` prefix replacement plus a one-octet transformation
scoped to the confirmed source network. Each rule retains direction, support,
contradictions, examples, active state, and a strength label. Rules are evidence
and are never auto-approved.

The queue is recomputed on request. This is intentional for the current small,
single-operator deployment; no Redis, Celery, Kafka, or materialized inventory
copy is required. The API boundary allows findings to be materialized later if
inventory size warrants it.

See [Host reconciliation API](host-completion-api.md) for the HTTP contract and
[Data model](data-model.md) for decision, state, and coverage definitions.
