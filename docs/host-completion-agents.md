# Host Completion Agents (Future Design Proposal)

Status: broader multi-Agent design proposal. Only capabilities explicitly
identified as current below are implemented.

Implementation note: the inventory reads are available through
`GET /api/host-completion/cases`,
`GET /api/host-completion/examples`, and
`GET /api/host-completion/analytics`. See
[Host Completion API](host-completion-api.md). A deterministic, no-LLM review
slice is also implemented through `GET /api/host-completion/review-queue` and
`POST /api/host-completion/decisions`: it infers rules on demand, persists
operator decisions, and applies accepted/corrected BMC links through existing
asset validation and audit paths. External Agent execution, verifier plugins,
stored/versioned templates, bulk review, and model-assisted behavior remain
proposed.

## Purpose

ipocket should eventually help operators complete and maintain a physical
Host's management-address information. A complete Host normally has at least:

- an active `OS` IP asset; and
- an active `BMC` IP asset (IPMI, iLO, iDRAC, Redfish-capable controller, or a
  similar management interface).

The first target workflow is to find Hosts for which one side of that pair is
missing, propose the missing address, and ask an operator to confirm or correct
the proposal. This is a Host-completion workflow, not merely BMC discovery.

The proposal deliberately assumes that:

- reverse DNS may not exist;
- private networks may not have useful DNS conventions;
- the Agent runner may be unable to reach the OS or BMC networks; and
- network probes, Redfish, IPMI, SNMP, and similar checks are optional evidence,
  not requirements for making progress.

## Existing foundation

The current data model already represents OS/BMC pairing through a shared
`host_id`. A Host may have linked assets grouped as `OS`, `BMC`, and other
types. The existing REST API can provide enough raw data for a proof of concept:

- `GET /hosts` lists Hosts.
- `GET /hosts/{host_id}` returns a Host with linked OS/BMC/other assets.
- `GET /ip-assets` returns active IP assets, including `type` and `host_id`.
- `POST /ip-assets` can create an IP asset.
- `PATCH /ip-assets/{ip_address}` can update its type and Host assignment.
- `GET /api/host-completion/cases` returns one-sided OS/BMC Hosts.
- `GET /api/host-completion/examples` returns complete OS/BMC Host examples.
- `GET /api/host-completion/analytics` returns read-only completion totals,
  confirmed-pair patterns, and active IP type counts.
- `GET /api/host-completion/review-queue` returns one deterministic suggestion
  or question, prioritized by incomplete source `/16` population.
- `POST /api/host-completion/decisions` stores Editor feedback and applies
  accepted or corrected BMC assets through normal inventory services.
- `/host-completion/analytics` visualizes analytics for operators without
  persisting Agent state; operators can reload it manually when needed.
- `/host-completion/review` gives Editors a one-at-a-time decision workflow.

The implemented deterministic slice centralizes basic completeness rules,
mapping inference, safety checks, and one-at-a-time orchestration. The broader
Agent design below remains useful for optional verification, richer scoping,
run visibility, and ambiguous cases.

## Design principles

1. Use several focused Agents or workers rather than one large autonomous Agent.
2. Keep candidate generation and scoring deterministic and explainable.
3. Treat human answers as first-class evidence.
4. Continue operating when DNS and network verification are unavailable.
5. Never allow an Agent to write directly to the database.
6. Apply accepted changes through ipocket validation, authorization, transactions,
   and audit logging.
7. Version learned rules and preserve the evidence behind every suggestion.
8. Prefer a domain API named for Host completion, not an API tied to a particular
   AI model or Agent implementation.

## Proposed Agent responsibilities

These responsibilities can initially be Python modules in one service. They do
not need to be separate processes or separately deployed services.

### Completeness Scanner

Classifies inventory into:

- complete Hosts with both OS and BMC assets;
- Hosts with OS assets but no BMC asset;
- Hosts with BMC assets but no OS asset;
- OS/BMC assets that are not linked to a Host; and
- ambiguous Hosts with multiple possible relationships.

The initial MVP should focus on active Hosts that already have an OS asset and
`host_id`, but do not have an active BMC asset. This population has the least
ambiguity. Later phases can handle the reverse direction and unlinked assets.

### Pattern Learning Agent

Learns address-mapping templates from currently confirmed OS/BMC pairs and from
later operator feedback. For example, confirmed pairs such as:

```text
10.10.1.20 -> 10.30.1.20
10.10.1.21 -> 10.30.1.21
10.10.2.15 -> 10.30.2.15
```

may support a rule that replaces the `10.10.0.0/16` prefix with
`10.30.0.0/16` while preserving the host bits.

Candidate rule forms may include:

- replacing one network prefix with another while preserving host bits;
- changing a particular octet;
- adding or subtracting a stable numeric offset;
- applying a mapping only within an IP Range, Project, Vendor, Site, or another
  future scope; and
- reversing a known OS-to-BMC rule to complete the OS side of a Host.

Rules should not be assumed to be global. Different network areas may use
different address plans. Each rule should track at least:

- support: confirmed pairs that match the rule;
- contradictions: confirmed pairs within scope that violate it;
- coverage: incomplete Hosts to which the rule can apply;
- accepted and rejected suggestions; and
- a derived confidence score.

### Candidate Generator

Applies eligible rules to an incomplete Host and produces one or more candidate
addresses. It can also detect whether a candidate:

- already exists in ipocket without a Host;
- exists with an unexpected type;
- is already linked to another Host; or
- does not yet exist and would need to be created after confirmation.

The first UI iteration should normally present one best candidate. Alternative
candidates can be retained for later review rather than overwhelming the user.

### Optional Verifiers

Verifiers add evidence when their dependencies are available. Possible future
plugins include DNS, TCP service checks, Redfish, IPMI, SNMP, DHCP, ARP, switch
MAC tables, CMDB, vCenter, or Prometheus.

Verifier unavailability is an ordinary `unknown` state, not a failed discovery
run and not negative evidence. For example:

```text
Template confidence: 86%
Network verification: unavailable
Final confidence: 86%
```

This keeps the core workflow useful from an Agent runner with no route to the
private management network. A verifier could later run on a separate, approved
runner inside that network.

### Review and Feedback Agent

Presents a small, answerable question similar to a people-confirmation workflow
in a photo application:

```text
Host:          server-42
Known OS IP:   10.10.4.42
Suggested BMC: 10.30.4.42
Confidence:    91%

Why?
- 18 confirmed Hosts follow this address mapping.
- One previous suggestion from this rule was rejected.
- Network verification is unavailable.

Is this the BMC IP for this Host?
```

Required decisions are:

- `ACCEPT`: create/link the proposed asset after a preview;
- `REJECT`: record negative evidence and do not repeat the same suggestion;
- `UNSURE`: postpone without penalizing the rule;
- `CORRECTED`: accept an operator-supplied address and use it as a strong new
  example; and
- `NO_MANAGEMENT_IP`: record that the Host should not be repeatedly queried for
  a management address.

The same flow can later ask for a missing OS IP when only a BMC IP is known.

## Self-improvement model

For the initial phases, self-improvement means improving explicit, inspectable
rules rather than autonomously retraining an AI model. The feedback loop is:

```text
confirmed pairs
    -> infer/version scoped templates
    -> generate and rank candidates
    -> ask an operator
    -> accept, reject, postpone, or correct
    -> update template evidence and scope
    -> generate better future suggestions
```

An accepted proposal increases support for the producing rule. A rejection
adds a contradiction and may cause a global rule to be narrowed to a particular
range or Project. A corrected address is the strongest feedback: it can create
a new rule or improve the scope of an existing one.

Rules must remain versioned and reversible. A new rule version should not rewrite
the historical reasoning behind older decisions.

### Active question selection

The system should not ask about every incomplete Host. It should prioritize
questions whose answers improve many later suggestions, such as:

- a new rule with high potential coverage;
- two competing rules for the same range;
- a medium-confidence suggestion whose answer resolves other cases; or
- a small sample from a large group that appears to follow one pattern.

After a few confirmations, the remaining candidates can receive higher
confidence. High-confidence bulk confirmation may be added later, but the first
version should use one-at-a-time review to gather clean feedback.

## Integration boundary

Agents should not access SQLite directly. Direct access would couple them to
the schema and bypass validation, role checks, conflict detection, transaction
boundaries, and Audit Log behavior.

The preferred boundary is a shared Host Completion application service:

```text
Host Completion UI ----+
                       |
External Agent --- HTTP API ---> Host Completion service
                                      | validation / RBAC / Audit
Internal worker ----------------------+
                                      |
                                  repositories
                                      |
                                   database
```

An external Agent uses the HTTP API. If an Agent later runs inside the FastAPI
application, it calls the same application service directly rather than making
a loopback HTTP request. The API and internal worker therefore share business
logic without giving either direct database control.

The API should use domain-oriented paths such as `/api/host-completion`, not
`/api/ai-agent`, so it remains useful to the UI, CLI, scheduled jobs, and future
non-AI implementations.

## API contract and proposed extensions

Exact schemas remain subject to implementation design and tests.

### List incomplete cases

```http
GET /api/host-completion/cases?status=pending&limit=100
```

The response should contain the Host, known OS/BMC assets, the missing side,
relevant scope metadata, and cursor-based pagination. The read-only endpoint is
implemented; its current contract is documented in
[Host Completion API](host-completion-api.md).

### List confirmed examples

```http
GET /api/host-completion/examples
```

This returns only the fields needed to infer patterns from confirmed pairs. It
must not expose secrets or unrelated sensitive notes. The read-only endpoint is
implemented.

### Submit a suggestion

Status: proposed, not implemented.

```http
POST /api/host-completion/suggestions
```

Example request:

```json
{
  "host_id": 42,
  "missing_type": "BMC",
  "candidate_ip": "10.30.4.42",
  "confidence": 0.91,
  "evidence": [
    {
      "type": "template_match",
      "rule": "10.10.0.0/16 -> 10.30.0.0/16",
      "support": 18,
      "contradictions": 1
    }
  ],
  "agent": {"name": "template-matcher", "version": "0.1.0"}
}
```

ipocket validates the IP, Host, duplicate status, conflicts, evidence format,
and confidence range before storing it.

### Record an operator decision

Status: proposed, not implemented.

```http
POST /api/host-completion/suggestions/{suggestion_id}/decision
```

Example correction:

```json
{
  "decision": "CORRECTED",
  "corrected_ip": "10.40.4.42"
}
```

### Apply an accepted suggestion

Status: proposed, not implemented.

```http
POST /api/host-completion/suggestions/{suggestion_id}/apply
```

Application should be transactional and idempotent. It creates an asset only
when necessary, applies the `OS` or `BMC` type, assigns the shared `host_id`,
marks the suggestion as applied, and writes an Audit Log entry. Separating the
decision from application preserves a preview/approval boundary; a later design
may combine them if the UI and safety model justify it.

## Possible persistence model

Names are provisional.

### `host_completion_rules`

- source and target network/template expression;
- direction (`OS_TO_BMC` or `BMC_TO_OS`);
- scope type and identifier;
- support, contradiction, accepted, and rejected counts;
- confidence, status, and version; and
- creation/update timestamps.

### `host_completion_suggestions`

- Host and known asset identifiers;
- missing type, candidate IP, and optional existing candidate asset;
- rule version, confidence, and structured evidence;
- pending/accepted/rejected/unsure/applied status; and
- creation and review metadata.

### `host_completion_feedback`

- suggestion identifier;
- decision and optional corrected IP;
- deciding user and timestamp; and
- optional comment or structured reason.

### `host_completion_runs`

- run type and Agent version;
- start/end time and status;
- counts for scanned Hosts, inferred rules, and suggestions; and
- sanitized errors or verifier availability information.

## Role of the company's small AI model

The core workflow must work without an LLM. Deterministic Python should perform
IP arithmetic, rule inference, scope selection, conflict checks, and confidence
calculation. The company's model can later help with:

- explaining evidence in clear language;
- comparing unusual Host naming patterns;
- summarizing ambiguous cases;
- generating concise operator questions; and
- selecting among already validated tools or candidates.

Credentials and raw secrets must never be included in model prompts. A model
failure or outage must not block pattern learning, candidate generation, or
human review.

## Proposed delivery phases

### Phase 0: analysis and offline prototype

- Measure the number of complete and incomplete Hosts.
- Export confirmed OS/BMC pairs through existing read APIs.
- Test deterministic template inference without persisting changes.
- Evaluate false positives and useful scoping dimensions.

### Phase 1: review-only vertical slice

- Add the Host Completion application service and domain API.
- Infer versioned templates from confirmed pairs.
- Generate at most one primary suggestion for OS-only Hosts.
- Add one-at-a-time `ACCEPT`, `REJECT`, `UNSURE`, `CORRECTED`, and
  `NO_MANAGEMENT_IP` review.
- Store suggestions, evidence, decisions, and Audit Log entries.
- Do not require DNS or network access.

### Phase 2: controlled application

- Preview and transactionally create/link accepted BMC assets.
- Add conflict and idempotency handling.
- Improve rule scope using accumulated feedback.
- Add operational metrics and run visibility.

### Phase 3: broader completion

- Handle BMC-only Hosts and unlinked OS/BMC assets.
- Add carefully reviewed bulk confirmation.
- Add optional verifier plugins and remote runners.
- Integrate the internal small model where it measurably improves explanations
  or ambiguous-case review.

## Open questions for implementation planning

- Does a complete Host require exactly one OS and one BMC address, or at least
  one of each?
- Which current metadata best defines rule scope: IP Range, Project, Vendor, or
  a future Site/Datacenter entity?
- What minimum support and contradiction thresholds should activate a rule?
- Should accepted decisions apply immediately or require a separate apply step?
- How long should `UNSURE` cases remain hidden before they may be asked again?
- Which Agent identity and permission model should be used for API access?
- Which inventory fields are safe to send to the company's model?
- Which network scopes, if any, may future verifier runners probe?

These questions do not block the proposed Phase 0 analysis.
