# UI notifications

ipocket uses compact success, information, warning, and error toasts for
page-level feedback. Field validation remains inline beside the affected form.
The shared visual treatment uses a neutral elevated surface, a semantic status
icon, and a keyboard-focusable dismiss control. Status color is reserved for
the icon so messages remain readable without relying on color alone. Toasts use
a short entrance transition that is disabled when reduced motion is requested.

## Shell flash messages

Server redirects use `_redirect_with_flash` from
`app/routes/ui/_utils/session.py` (re-exported by `app/routes/ui/utils.py`). The
signed flash cookie is consumed by `app/routes/ui/_utils/rendering.py`, rendered
by `app/templates/base.html`, and dismissed by `app/static/toast.js`. Messages
are truncated to the safe cookie payload limit before storage.

```python
return _redirect_with_flash(
    request,
    "/ui/ip-assets",
    "IP asset updated.",
    message_type="success",
)
```

For a native download link, `data-toast-message` and `data-toast-type` can show
non-blocking feedback without intercepting the download:

```html
<a
  href="/export/ip-assets.csv"
  data-toast-message="IP assets export started."
  data-toast-type="info"
>
  Export CSV
</a>
```

## React pages

React pages own transient feedback produced without a full redirect. Keep the
message in page/component state and render it with the shared `.toast-*` classes
from `app/static/css/utility-pages.css`. Clear or replace it after the next
relevant action and provide an accessible dismiss button when it persists.

Connector job toasts are returned as structured job result data; field-level
connector validation stays in the form.

## Defaults

- Shell auto-dismiss: approximately four seconds.
- IP Assets action toasts auto-dismiss after approximately four seconds; a new
  toast replaces and restarts the timer for the previous one.
- Shell location: top-right.
- Use success/info for completed actions, warning for recoverable partial
  outcomes, and error for page-level failures.
- Keep the shared `.toast-*` markup and styles so server-rendered and React
  notifications remain visually consistent.
- Never replace field-specific validation with a toast.
