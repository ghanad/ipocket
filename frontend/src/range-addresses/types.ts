export type AddressStatus = "used" | "free";
export type RangeStatusFilter = "all" | AddressStatus;

export interface ColorOption {
  id: number;
  name: string;
  color: string;
}

export interface RangeAddressRow {
  ip_address: string;
  status: AddressStatus;
  asset_id: number | null;
  project_id: number | null;
  project_name: string | null;
  project_color: string;
  project_unassigned: boolean;
  asset_type: string | null;
  host_pair: string;
  tags: ColorOption[];
  notes: string;
  policy: { can_add: boolean; can_edit: boolean };
}

export interface RangeAddressFilters {
  q: string;
  project_id: string;
  type: string;
  tags: string[];
  status: RangeStatusFilter;
  page: number;
  per_page: number;
}

export interface RangeAddressesResponse {
  range: {
    id: number;
    name: string;
    cidr: string;
    total_usable: number;
    used: number;
    free: number;
  };
  filters: {
    projects: ColorOption[];
    tags: ColorOption[];
    types: string[];
    policy: { can_write: boolean };
  };
  addresses: RangeAddressRow[];
  query: RangeAddressFilters;
  pagination: {
    page: number;
    per_page: number;
    total: number;
    total_pages: number;
    has_prev: boolean;
    has_next: boolean;
    start_index: number;
    end_index: number;
  };
}

export interface AddressFormValues {
  ip_address: string;
  type: string;
  project_id: string;
  tags: string[];
  notes: string;
}
