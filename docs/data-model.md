# Data Model (MVP)

## IPAsset
Required:
- ip_address (unique)
- subnet
- gateway
- type

Fields:
- ip_address: unique string
- subnet: string (CIDR or label)
- gateway: string
- project_id: optional reference to Project
- owner_id: optional reference to Owner
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
- name (unique)
- contact (optional)

## User
- username (unique)
- hashed_password
- role: Viewer | Editor | Admin
- is_active
