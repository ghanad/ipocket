export interface ManagementSummary {
  active_ip_total: number;
  archived_ip_total: number;
  host_total: number;
  vendor_total: number;
  project_total: number;
}

export interface RangeUtilization {
  id: number;
  name: string;
  cidr: string;
  total_usable: number;
  used: number;
  free: number;
  utilization_percent: number;
}

export interface ManagementOverview {
  summary: ManagementSummary;
  utilization: RangeUtilization[];
}
