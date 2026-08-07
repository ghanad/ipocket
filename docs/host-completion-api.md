# Host reconciliation API

Host reconciliation is deterministic and human-in-the-loop. All endpoints
require ipocket authentication; mutations require an Editor. The in-process
`ipocket_agent` package reads an inventory projection and never writes SQLite.

## Read current findings

```http
GET /api/host-completion/findings
GET /api/host-completion/findings/next
Authorization: Bearer <token>
```

Findings are `CREATE_HOST`, `COMPLETE_HOST`, `UNMATCHED_ASSET`, or `CONFLICT`.
One OS/BMC pair produces one physical-host proposal. A finding includes its
assets, proposed Host name when relevant, evidence, reasons, `match_strength`,
rule IDs, `proposal_id`, and `inventory_fingerprint`. Strength is an operational
label, not a probability.

`CREATE_HOST` uses the fixed inventory convention `server_<bmc-ip>`.
`COMPLETE_HOST` targets an existing Host. Weak/ambiguous evidence never forces a match;
ambiguity, incompatible types, and already-linked counterparts are conflicts.

## Read summary and rules

```http
GET /api/host-completion/summary
Authorization: Bearer <token>
```

The summary exposes active OS/BMC totals, attached/unresolved counts, proposed
Host creations, incomplete Hosts, conflicts, exceptions, discovered rule
support/contradictions/examples, reconciliation coverage, and unexplained
active assets. Coverage is `(RESOLVED + PROPOSED + EXCEPTION) / active OS/BMC`.

## Apply an operator decision

```http
POST /api/host-completion/findings/decisions
Authorization: Bearer <editor-token>
Idempotency-Key: review-2026-08-07-001
Content-Type: application/json

{
  "proposal_id": "...",
  "inventory_fingerprint": "...",
  "decision": "ACCEPT"
}
```

Supported decisions are `ACCEPT`, `CORRECT`, `WRONG_PAIR`, `UNSURE`,
`EXCEPTION`, `ATTACH_EXISTING`, and `DEACTIVATE`. `CORRECT` supplies the
operator-known counterpart address and its direction, for example:

```json
{
  "proposal_id": "...",
  "inventory_fingerprint": "...",
  "decision": "CORRECT",
  "counterpart_ip": "10.30.4.42",
  "counterpart_type": "BMC"
}
```

When the known asset is OS, the UI asks for its BMC address. When the known
asset is BMC, it asks for its OS address. If the counterpart asset does not yet
exist, ipocket creates it. It then creates or reuses `server_<bmc-ip>` and links
both assets atomically. Operators never need database Asset or Host IDs for this
normal workflow. `ATTACH_EXISTING` with `target_host_id` remains an API-level
advanced action.

Before applying, ipocket regenerates the finding inside the transaction and
compares both proposal ID and fingerprint. A stale proposal returns `409` and
does not partially apply. Host create/reuse, asset links/archive, operator
decision, and audit entries commit atomically. Repeating the same idempotency
key returns the original result without duplicate Hosts, links, or decisions.

Only `WRONG_PAIR` is negative evidence against a discovered mapping. `UNSURE`
and `EXCEPTION` do not increase rule contradictions.

The older `/analytics`, `/cases`, `/examples`, `/review-queue`, and `/decisions`
routes remain temporarily for prototype migration, but are authenticated and
the current UI uses the proposal-based endpoints above.

## Logical boundary

```text
ipocket UI -> authenticated ipocket API -> ipocket_agent analysis
                                          |
operator decision -> ipocket transaction API -> inventory + audit log
```

There is no LLM, embeddings store, external queue, separate authentication
system, or duplicated authoritative inventory.
