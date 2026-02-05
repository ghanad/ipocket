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


## BMC auto-host linkage
- On create, when an IPAsset has `type=BMC` and `host_id` is omitted/null, ipocket auto-links it to a Host named exactly `server_{ip_address}`.
- If that Host already exists, it is reused (no duplicate Host creation).
- If `host_id` is provided explicitly, no auto-host creation is performed.
