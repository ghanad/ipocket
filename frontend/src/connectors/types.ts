export type ConnectorName = "vcenter" | "prometheus" | "elasticsearch" | "cassandra" | "ceph" | "kubernetes";
export type ConnectorTab = "overview" | ConnectorName;
export type ConnectorMode = "dry-run" | "apply";
export type FieldValue = string | boolean;

export interface ConnectorFieldSchema {
  name: string;
  label: string;
  type: "text" | "url" | "password" | "number" | "select" | "checkbox";
  required: boolean;
  default: FieldValue;
  placeholder: string;
  span: boolean;
  secret: boolean;
  min?: number;
  max?: number;
  options?: string[];
}

export interface ConnectorSchema {
  name: ConnectorName;
  display_name: string;
  description: string;
  kind: string;
  help: string;
  command: string;
  fields: ConnectorFieldSchema[];
  run_url: string;
}

export interface ConnectorsConfig {
  connectors: ConnectorSchema[];
  asset_types: string[];
  policy: { can_dry_run: boolean; can_apply: boolean; apply_message: string };
  jobs_url: string;
  poll_interval_ms: number;
}

export interface JobStart {
  job_id: string;
  connector: ConnectorName;
  status: "queued";
  poll_url: string;
}

export interface ConnectorJob {
  job_id: string;
  connector: ConnectorName;
  active_tab: ConnectorName;
  status: "queued" | "running" | "completed" | "failed";
  form_state: Record<string, FieldValue>;
  logs: string[];
  toast_messages: Array<{ type: string; message: string }>;
  polling: boolean;
}
