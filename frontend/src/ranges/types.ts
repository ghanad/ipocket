export interface RangeRow {
  id: number;
  name: string;
  cidr: string;
  notes: string | null;
  total_usable: number | null;
  used: number | null;
  free: number | null;
  utilization_percent: number | null;
}

export interface RangesResponse {
  ranges: RangeRow[];
}

export interface RangeFormValues {
  name: string;
  cidr: string;
  notes: string;
}

export interface RangesBootstrap {
  mode: "create" | "edit" | "delete";
  range?: Pick<RangeRow, "id" | "name" | "cidr" | "notes">;
  values?: RangeFormValues;
  confirm_name?: string;
  errors?: string[];
}
