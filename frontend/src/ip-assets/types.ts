export type AssetType = "OS" | "BMC" | "VM" | "VIP" | "OTHER";
export type TagMode = "tag_any" | "tag_all" | "tag_not";

export interface ColorOption {
  id: number;
  name: string;
  color: string | null;
}

export interface HostOption {
  id: number;
  name: string;
}

export interface AssetRow {
  id: number;
  ip_address: string;
  type: AssetType;
  project_id: number | "";
  project_name: string;
  project_color: string | null;
  project_unassigned: boolean;
  host_id: number | "";
  host_name: string;
  tags: Array<{ name: string; color: string }>;
  notes: string;
  unassigned: boolean;
  delete_requires_exact_ip: boolean;
  can_auto_host: boolean;
}

export interface AssetFilters {
  q: string;
  project_id: string;
  type: string;
  unassigned_only: boolean;
  archived_only: boolean;
  tag_any: string[];
  tag_all: string[];
  tag_not: string[];
  page: number;
  per_page: number;
}

export interface AssetsResponse {
  assets: AssetRow[];
  filters: {
    projects: ColorOption[];
    hosts: HostOption[];
    tags: ColorOption[];
    types: AssetType[];
    normalized: AssetFilters;
  };
  pagination: {
    page: number;
    per_page: number;
    total: number;
    total_pages: number;
  };
  can_edit: boolean;
}

export interface AssetFormValues {
  ip_address: string;
  type: AssetType;
  project_id: string;
  host_id: string;
  tags: string[];
  notes: string;
}

export interface BulkValues {
  type: string;
  projectMode: "" | "assign" | "unassign";
  project_id: string;
  tags_to_add: string[];
  tags_to_remove: string[];
  notes_mode: "" | "set" | "clear";
  notes: string;
}
