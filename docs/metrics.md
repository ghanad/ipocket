# Prometheus Metrics

The app exposes Prometheus metrics at:

- GET /metrics

## MVP minimum metrics

### ipam_ip_total
Total number of IPAsset records (including archived, unless specified otherwise).

### ipam_ip_archived_total
Total number of archived (soft-deleted) IPAsset records.

### ipam_ip_unassigned_owner_total
Number of non-archived IPAsset records missing Owner.

### ipam_ip_unassigned_project_total
Number of non-archived IPAsset records missing Project.

### ipam_ip_unassigned_both_total
Number of non-archived IPAsset records missing both Owner and Project.

## Notes
- Metrics must be consistent and test-covered.
- Metrics should not require external services.
