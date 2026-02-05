# Data Model (MVP)

## IPAsset
Required:
- ip_address (unique)
- type

Optional:
- subnet
- gateway

Fields:
- ip_address: unique string
- subnet: optional string (CIDR or label)
- gateway: optional string
- project_id: optional reference to Project
- owner_id: optional reference to Owner
- type: VM | OS | BMC | VIP | OTHER
- notes: optional text
- archived: boolean (soft delete)
- created_at, updated_at timestamps

Notes:
- We use **soft delete** (archived) instead of hard delete.
- Legacy input aliases `IPMI_ILO` and `IPMI_iLO` are accepted and normalized to `BMC`.
- `OS` is for an IP configured on a host operating system (for example, a physical server NIC).
- `BMC` is for out-of-band management interfaces (iLO/iDRAC/IPMI), separate from OS network IPs.

## Project
- name (unique)
- description (optional)

## Owner
- name (unique)
- contact (optional)

## User
- username (unique)
- hashed_password
- role: Viewer | Editor | Admin
- is_active


## Service discovery labels
- `/sd/node` exposes `project`, `owner`, and `type` labels for each non-archived IPAsset target and can group targets with `group_by`.
- Missing `project` or `owner` values are emitted as `unassigned`.
