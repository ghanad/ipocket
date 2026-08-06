export interface HostCompletionBreakdown {
  os_only: number;
  bmc_only: number;
  unlinked: number;
}

export interface HostCompletionPattern {
  source_prefix: string;
  target_prefix: string;
  support: number;
  contradictions: number;
  coverage_percent: number;
}

export interface HostCompletionIPTypeCounts {
  BMC: number;
  OS: number;
  VM: number;
  unknown: number;
}

export interface HostCompletionAnalytics {
  total_hosts: number;
  complete_hosts: number;
  incomplete_hosts: number;
  breakdown: HostCompletionBreakdown;
  confirmed_pairs: number;
  patterns: HostCompletionPattern[];
  ip_type_counts: HostCompletionIPTypeCounts;
}
