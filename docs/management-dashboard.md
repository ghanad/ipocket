# Management dashboard

The management dashboard provides a focused, read-only snapshot of inventory health and capacity. Its
inventory footprint section keeps active IPs prominent and exposes direct links to the related inventory,
archived records, Hosts, Vendors, and Projects. Use **Refresh data** to re-request the current snapshot.
It also surfaces:

- Active IP count (non-archived IP assets)
- Archived IP count (soft-deleted IP assets)
- Host count
- Vendor count
- Project count
- Subnet utilization (used vs. free IPs per CIDR range, with links to address lists)

Each range has a capacity label derived from its utilization: **Available** below 70%, **Monitor** from
70% through 89.9%, and **Action needed** at 90% or above. These labels are UI-only guidance; the
underlying used/free counts remain the source of truth.

The Vendors total opens the **Vendors** tab in Library (`/ui/projects?tab=vendors`). The legacy
`/ui/vendors` URL redirects there so existing bookmarks continue to work without opening a second UI.

## Where to find it

Use the **Management** entry in the left navigation or visit `/ui/management`.

## Reviewing free vs. used addresses

In the Subnet Utilization table, click the **Used** or **Free** counts to open the per-range
address list. The table shows each IP once with a colored **Used/Free** status badge plus the
current **Project** and **Type** when assigned. The **IP Ranges** page also includes the same
utilization table with the same links for quick review.
