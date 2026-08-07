export interface ReconciliationRule {
  id: string;
  direction: "OS_TO_BMC";
  transformation: string;
  source_pattern: string;
  target_pattern: string;
  strength: "STRONG" | "MODERATE" | "WEAK" | "INACTIVE";
  active: boolean;
  support: number;
  contradictions: number;
  examples: string[];
}

export interface HostCompletionAnalytics {
  active_os_assets: number;
  active_bmc_assets: number;
  os_attached_to_hosts: number;
  bmc_attached_to_hosts: number;
  unresolved_os_assets: number;
  unresolved_bmc_assets: number;
  proposed_host_creations: number;
  incomplete_hosts: number;
  conflicts: number;
  explicit_exceptions: number;
  discovered_rules: number;
  rule_support: number;
  rule_contradictions: number;
  reconciliation_coverage: number;
  unexplained_active_assets: number;
  active_assets: number;
  states: {
    RESOLVED: number;
    PROPOSED: number;
    UNMATCHED: number;
    CONFLICT: number;
    EXCEPTION: number;
  };
  rules: ReconciliationRule[];
}
