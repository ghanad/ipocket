export interface HostDetailTag {
  name: string;
  color: string;
}

export interface HostDetailAsset {
  id: number;
  ip_address: string;
  type: "OS" | "BMC" | "VM" | "VIP" | "OTHER";
  project: {
    name: string;
    color: string | null;
  } | null;
  tags: HostDetailTag[];
  notes: string;
}

export interface HostDetailResponse {
  host: {
    id: number;
    name: string;
    vendor: string;
    notes: string;
  };
  summary: {
    linked_count: number;
    os_count: number;
    bmc_count: number;
    other_count: number;
  };
  groups: {
    os: HostDetailAsset[];
    bmc: HostDetailAsset[];
    other: HostDetailAsset[];
  };
}
