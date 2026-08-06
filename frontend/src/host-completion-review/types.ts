export type HostCompletionReviewMode = "ASK" | "SUGGEST";

export type HostCompletionCaseType =
  | "UNLINKED_OS_PAIR"
  | "UNLINKED_BMC_PAIR"
  | "UNLINKED_OS"
  | "UNLINKED_BMC"
  | "HOST_MISSING_BMC"
  | "HOST_MISSING_OS";

export interface HostCompletionQueueAsset {
  address: string;
  hostname: string | null;
}

export interface HostCompletionReviewItem {
  case_type: HostCompletionCaseType;
  host_id: number | null;
  os_asset: HostCompletionQueueAsset | null;
  bmc_asset: HostCompletionQueueAsset | null;
  would_create_host: boolean;
  mode: HostCompletionReviewMode;
  candidate_ip: string | null;
  confidence: number | null;
  evidence: string[];
  reason_text: string;
}

export interface HostCompletionReviewQueue {
  item: HostCompletionReviewItem | null;
  remaining: number;
}

export type HostCompletionDecision =
  | "ACCEPT"
  | "REJECT"
  | "CORRECTED"
  | "UNSURE"
  | "NO_BMC"
  | "NO_OS"
  | "CREATE_HOST_ONLY"
  | "ATTACH_EXISTING"
  | "DEACTIVATE";

export interface HostCompletionDecisionPayload {
  case_type?: HostCompletionCaseType;
  mode: HostCompletionReviewMode;
  host_id?: number;
  os_address?: string;
  bmc_address?: string;
  decision: HostCompletionDecision;
  candidate_ip?: string;
  corrected_ip?: string;
  host_name?: string;
}

export interface HostCompletionDecisionResponse {
  id: number;
  decision: HostCompletionDecision;
  applied_ip: string | null;
  host_id: number | null;
}
