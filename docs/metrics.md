# Metrics

The app exposes Prometheus metrics at `GET /metrics`:

- `ipam_ip_total`: total number of IP records (including archived).
- `ipam_ip_archived_total`: number of archived IP records.
- `ipam_ip_unassigned_project_total`: number of active IP records without a project assignment.


Note: Vendor catalog/host vendor selection does not introduce new Prometheus metrics in this release.
