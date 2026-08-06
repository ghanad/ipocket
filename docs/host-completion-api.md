# Host Completion API

ipocket exposes a read-only domain API for independently developed Host
completion Agents. The Agent is expected to run outside the main application
and communicate over HTTP. An internal scheduled worker may later call the same
application service directly, but neither integration should access the database
directly.

This API is an inventory boundary, not an AI implementation. ipocket owns Host
completeness semantics and returns stable, validated data; the external Agent
owns template inference, candidate generation, confidence scoring, and question
selection.

## Current endpoints

Both current endpoints are public, consistent with the existing inventory read
API. They expose no credentials or Host/IP notes. Future suggestion and apply
operations will require an explicit authorization design before implementation.

### List incomplete Hosts

```http
GET /api/host-completion/cases?missing=any&limit=100&cursor=123
```

An incomplete case has exactly one active side of an OS/BMC Host pair:

- one or more active OS assets and no active BMC assets; or
- one or more active BMC assets and no active OS assets.

Hosts with neither type and Hosts that already have both types are excluded.
Archived assets do not contribute to completeness.

Query parameters:

- `missing`: `any` (default), `OS`, or `BMC`;
- `limit`: `1` to `500`, default `100`; and
- `cursor`: return Host IDs greater than this value.

Example response:

```json
{
  "items": [
    {
      "host_id": 42,
      "host_name": "server-42",
      "vendor": "Dell",
      "os_assets": [
        {
          "id": 100,
          "ip_address": "10.10.4.42",
          "project_id": 7,
          "project_name": "payment"
        }
      ],
      "bmc_assets": [],
      "missing": "BMC"
    }
  ],
  "next_cursor": null
}
```

### List confirmed examples

```http
GET /api/host-completion/examples?limit=100&cursor=123
```

This returns Hosts with at least one active OS asset and at least one active BMC
asset. An external pattern-learning Agent can use these shared-`host_id` pairs
as confirmed examples. The endpoint uses the same cursor and limit behavior as
`cases`.

## Pagination

Results are ordered by increasing Host ID. When `next_cursor` is not null, pass
that value as `cursor` in the next request. A null value means there is no next
page for the current filter.

## Current boundary

The current release does not store Agent suggestions, learned templates, or
operator feedback, and it does not apply proposed OS/BMC links. Those workflows
remain future work described in
[Host Completion Agents](host-completion-agents.md). Until an approved write
contract exists, an external Agent should treat these endpoints as read-only
training and case-discovery inputs.

## Internal architecture

- `app/routes/api/host_completion.py` defines the HTTP/OpenAPI contract.
- `app/services/host_completion.py` defines the application-service boundary
  shared with possible future internal workers.
- `app/repository/host_completion.py` performs the inventory queries.

This layering keeps Agent logic out of ipocket while preventing every consumer
from reimplementing database and completeness semantics.
