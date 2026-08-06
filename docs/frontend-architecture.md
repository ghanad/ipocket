# Frontend architecture

ipocket uses React/Vite/TypeScript for its normal browser pages. FastAPI and
Jinja remain a deliberately small server-rendered boundary: they provide the
shared document shell, sidebar, session/flash context, and React mount points.
Page data and mutations use focused `/api/ui/...` JSON endpoints.

## React entries

The 15 production entries are registered in `frontend/vite.config.ts`:

- `about`
- `account-password`
- `audit-log`
- `connectors`
- `data-ops`
- `host-detail`
- `hosts`
- `ip-asset-detail`
- `ip-assets`
- `library`
- `login`
- `management`
- `range-addresses`
- `ranges`
- `users`

`tests/react_ui_manifest.py` is the canonical manifest used by mount, endpoint,
Vite-entry, and bundle-reference tests.

## Build artifacts

Run the frontend build from `frontend/`:

```bash
npm ci
npm run build
```

Vite writes entry bundles to
`app/static/react/<entry>/<entry>.js` and shared chunks to
`app/static/react/shared/`. The entire `app/static/react/` directory is ignored
generated output: do not edit or commit it. CI and the Docker frontend stage
rebuild it from the tracked TypeScript sources and lockfile.

## Server-rendered compatibility boundary

Jinja templates must not be removed merely because their normal page content is
React. Each React page still needs a lightweight template containing its mount
element and module script. The following server-rendered flows are also retained:

- direct IP Asset create, edit, and delete-confirmation forms;
- HTML POST validation/results for Data Operations and Connectors;
- HTML POST validation/bootstrap flows for Hosts, Ranges, Users, Account
  Password, and Library;
- redirect routes that open the corresponding React drawer from older URLs;
- the Hosts `HX-Request` table partial.

These routes are compatibility paths, not a second primary UI. New interactive
features should be implemented in React and exposed through a server-authorized
JSON endpoint.

## Shared browser assets

`app/templates/base.html` loads the shared stylesheet, favicon, shell toast
handler, tag picker, and searchable Host selector used by retained direct forms.
The Library compatibility templates additionally use their focused drawer and
catalog scripts. HTMX and Alpine remain available only for retained
server-rendered compatibility paths.

## Authentication and authorization

The browser client uses the existing same-origin session cookie. Authorization
is always repeated by FastAPI dependencies:

- public inventory reads return `can_edit=false` for signed-out/View-only users;
- About, Audit Log, Data Operations, Connectors, Library data, and detail pages
  require authentication where their routes specify it;
- Users is Superuser-only;
- inventory and catalog mutations, import apply, and connector apply require an
  Editor or Superuser;
- password changes are self-only.

React hiding or disabling a control is presentation only and is never the
authorization boundary.

## Adding a page

1. Add `frontend/src/<entry>/main.tsx` plus component and API tests.
2. Register the entry in `frontend/vite.config.ts`.
3. Add a lightweight Jinja mount with the root element, endpoint data attributes,
   and `/static/react/<entry>/<entry>.js` module script.
4. Add one record to `tests/react_ui_manifest.py`.
5. Keep authorization in the API dependency and handle expired-session redirects
   in the page adapter.
6. Update this document if the page adds or removes a compatibility route.
