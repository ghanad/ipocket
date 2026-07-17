export interface DataOpsConfig {
  policy: { can_apply: boolean };
  upload: { max_bytes: number; max_size: string };
  samples: { hosts: string; ip_assets: string };
  imports: Record<ImportKind, string>;
  exports: {
    bundle_json: string;
    bundle_zip: string;
    ip_assets_csv: string;
    ip_assets_json: string;
    hosts_csv: string;
    hosts_json: string;
    vendors_csv: string;
    vendors_json: string;
    projects_csv: string;
    projects_json: string;
  };
}

export interface ImportCount {
  would_create: number;
  would_update: number;
  would_skip: number;
}

export interface ImportIssue {
  location: string;
  message: string;
}

export interface ImportResult {
  summary: {
    vendors: ImportCount;
    projects: ImportCount;
    hosts: ImportCount;
    ip_assets: ImportCount;
    total: ImportCount;
  };
  errors: ImportIssue[];
  warnings: ImportIssue[];
}

export interface NmapResult {
  discovered_up_hosts: number;
  new_ips_created: number;
  existing_ips_seen: number;
  errors: string[];
  new_assets: Array<{ id: number; ip_address: string }>;
}

export type DataOpsTab = "import" | "export";
export type ImportKind = "bundle" | "csv" | "nmap";
export type ImportMode = "dry-run" | "apply";
