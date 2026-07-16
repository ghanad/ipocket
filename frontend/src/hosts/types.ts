export interface HostIPLink {
  id: number;
  ip_address: string;
}

export interface HostTag {
  name: string;
  color: string;
}

export interface HostRow {
  id: number;
  name: string;
  notes: string | null;
  vendor: string | null;
  project_count: number;
  project_id: number | null;
  project_name: string;
  project_color: string;
  ip_count: number;
  os_ip_links: HostIPLink[];
  bmc_ip_links: HostIPLink[];
  ip_tags: HostTag[];
}

export interface FilterOption {
  id: number;
  name: string;
  color?: string | null;
}

export interface HostsResponse {
  hosts: HostRow[];
  filters: {
    projects: FilterOption[];
    vendors: FilterOption[];
    tags: FilterOption[];
  };
  pagination: {
    page: number;
    per_page: number;
    total: number;
    total_pages: number;
  };
  can_edit: boolean;
}

export interface HostFormValues {
  name: string;
  vendor_id: string;
  project_id: string;
  os_ips: string;
  bmc_ips: string;
  notes: string;
}

export interface HostFilters {
  q: string;
  project_id: string;
  unassigned_only: boolean;
  status: string;
  vendor_id: string;
  tags: string[];
  page: number;
  per_page: number;
}
