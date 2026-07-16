export type AssetType = "OS" | "BMC" | "VM" | "VIP" | "OTHER";

export interface ColorOption {
  id: number;
  name: string;
  color: string | null;
}

export interface HostOption {
  id: number;
  name: string;
}

export interface AssetDetail {
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
  host_pair_assets: Array<{ id: number; ip_address: string }>;
}

export interface AuditLog {
  created_at: string;
  user: string;
  action: "CREATE" | "UPDATE" | "DELETE" | string;
  changes: { summary: string; raw: string };
}

export interface DetailResponse {
  asset: AssetDetail;
  audit_logs: AuditLog[];
  metadata: {
    projects: ColorOption[];
    hosts: HostOption[];
    tags: ColorOption[];
    types: AssetType[];
  };
  can_edit: boolean;
  delete_requires_exact_ip: boolean;
  auto_host_enabled: boolean;
  can_auto_host: boolean;
}

export interface EditValues {
  type: AssetType;
  project_id: string;
  host_id: string;
  tags: string[];
  notes: string;
}
