export type AuditLogRow = {
  id?: number;
  created_at: string;
  target_label: string;
  username: string;
  action: string;
  changes: string;
};

export type AuditLogQuery = {
  page: number;
  per_page: number;
};

export type AuditLogResponse = {
  audit_logs: AuditLogRow[];
  pagination: AuditLogQuery & {
    total: number;
    total_pages: number;
  };
  query: AuditLogQuery;
};
