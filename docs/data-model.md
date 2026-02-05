# Data model

## IPAsset
- `ip_address` (unique)
- `subnet`
- `gateway`
- `project_id` (optional)
- `type` (`VM`, `OS`, `BMC`, `VIP`, `OTHER`)
- `host_id` (optional)
- `notes` (optional)
- `archived` (soft delete)
- timestamps (`created_at`, `updated_at`)

## Project
- `name` (unique)
- `description` (optional)
