# Prometheus Metrics

The app exposes Prometheus metrics at:

- GET /metrics

## MVP minimum metrics

### ipam_ip_total
Total number of IPAsset records, including archived.

### ipam_ip_archived_total
Total number of archived (soft-deleted) IPAsset records.

### ipam_ip_unassigned_owner_total
Number of non-archived IPAsset records missing Owner (owner_id is NULL).

### ipam_ip_unassigned_project_total
Number of non-archived IPAsset records missing Project (project_id is NULL).

### ipam_ip_unassigned_both_total
Number of non-archived IPAsset records missing both Owner and Project.

## Example scrape config

```yaml
scrape_configs:
  - job_name: ipocket
    static_configs:
      - targets: ["localhost:8000"]
```

## Notes
- Metrics are computed from database state at request time.
- Archived IPs are excluded from all unassigned metrics.
- Metrics should not require external services.


## Related discovery endpoint
- `GET /sd/node` provides Prometheus HTTP SD target groups for node-level scrapes. See `/docs/service-discovery.md`.
