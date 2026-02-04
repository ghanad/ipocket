# Data Model (MVP)

## IPAsset
Required:
- ip_address (unique)

Fields:
- subnet: string (CIDR or label)
- gateway: string
- project: optional reference to Project
- owner: optional reference to Owner
- type: VM | PHYSICAL | IPMI_ILO | VIP | OTHER
- notes: optional text
- archived: boolean (soft delete)
- created_at, updated_at timestamps

Notes:
- We use **soft delete** (archived) instead of hard delete.

## Project
- name (unique)
- description (optional)

## Owner
- name
- contact (optional)

## User
- username
- role: Viewer | Editor | Admin
- is_active
