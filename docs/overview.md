# ipocket overview

ipocket is a lightweight IP inventory app to track addresses and their project assignment.

## Highlights
- CRUD API for IP records (including permanent delete endpoint for editors/admins)
- Project management
- Needs Assignment UI for project-only assignment
- IP list/detail UI provides a Delete action for editors/admins with a mandatory confirmation textbox (type exact IP) before permanent deletion
- Prometheus metrics on `/metrics`
- Prometheus SD endpoint on `/sd/node` with project grouping

## Note
Owner support has been removed in development phase, so assignment is now project-only.


## Hosts

Hosts can be linked to a vendor from the shared **Vendors** catalog.

- Hosts list supports inline edit for name, vendor, and notes.

## Vendors

Vendors are managed as a dedicated list (create/edit) and are selectable when creating or editing Hosts (API and UI).
