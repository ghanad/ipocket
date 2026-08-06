export type LibraryTab = "projects" | "vendors" | "tags";
export type DrawerMode = "create" | "edit" | "delete" | null;

export interface ProjectRow {
  id: number;
  name: string;
  description: string | null;
  color: string;
  usage_count: number;
}

export interface VendorRow {
  id: number;
  name: string;
  usage_count: number;
}

export interface TagRow {
  id: number;
  name: string;
  color: string;
  usage_count: number;
}

export interface LibraryResponse<T> {
  items: T[];
  can_edit: boolean;
  default_color?: string;
  suggested_color?: string;
}

export interface LibraryBootstrap {
  tab?: LibraryTab;
  mode?: Exclude<DrawerMode, null>;
  entity_id?: number;
  values?: Record<string, string>;
  confirm_name?: string;
  errors?: string[];
}
