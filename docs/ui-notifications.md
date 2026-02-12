# UI Notifications (Toasts)

ipocket includes a lightweight toast system for global feedback (success/error/info). Toasts appear in the top-right corner and auto-dismiss after a few seconds. Use them for actions like create/update/import/export; keep inline form errors for field-level validation.

## What it is
- A small toast container is rendered in `base.html` so it works across all UI pages.
- Toasts auto-dismiss after ~4 seconds and can be closed manually.
- Supported types: `success`, `info`, `error`, `warning` (optional).

## Triggering from the backend (flash messages)
Use the session-backed flash helper in `app/routes/ui.py`. These messages are one-time and cleared after they are rendered.

**Example: success after a POST redirect**
```python
return _redirect_with_flash(
    request,
    "/ui/projects",
    "Project created.",
    message_type="success",
)
```

**Example: unexpected error redirect**
```python
return _redirect_with_flash(
    request,
    "/ui/ip-assets",
    "Something went wrong while saving the asset.",
    message_type="error",
)
```

## Client-side triggers (minimal)
To trigger a toast on the client (for example, when starting an export), add `data-toast-message` and optional `data-toast-type` attributes to a link or button:

```html
<a
  href="/export/ip-assets.csv"
  data-toast-message="IP assets export started."
  data-toast-type="info"
>
  Export CSV
</a>
```

## Guidelines
- **Use toasts for global feedback** (created/updated/imported/exported, unexpected errors).
- **Keep inline validation errors** inside forms; do not replace field-level errors with toasts.
- Prefer `success`/`info` for positive feedback and `error` for failures.
- Bulk edits on the IP Assets page surface success/error results as toast messages after redirecting back to the list.
- Connectors UI (`/ui/connectors?tab=vcenter`) uses toasts for run outcomes (`success` / `warning` / `error`) while keeping field-level validation inline.

## Defaults
- Auto-dismiss: ~4 seconds
- Location: top-right
