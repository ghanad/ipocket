export type ReconciliationFindingType =
  | "CREATE_HOST"
  | "COMPLETE_HOST"
  | "UNMATCHED_ASSET"
  | "CONFLICT";

export type ReconciliationDecision =
  | "ACCEPT"
  | "CORRECT"
  | "WRONG_PAIR"
  | "UNSURE"
  | "EXCEPTION"
  | "ATTACH_EXISTING"
  | "DEACTIVATE";

export interface ReconciliationAsset {
  id: number;
  ip_address: string;
  type: "OS" | "BMC" | "VM" | "VIP" | "OTHER";
  host_id: number | null;
}

export interface ReconciliationFinding {
  finding_type: ReconciliationFindingType;
  state: "PROPOSED" | "UNMATCHED" | "CONFLICT";
  proposal_id: string;
  inventory_fingerprint: string;
  host_id: number | null;
  proposed_host_name: string | null;
  assets: ReconciliationAsset[];
  candidate_ips: string[];
  match_strength: "STRONG" | "MODERATE" | "WEAK" | "INACTIVE" | null;
  evidence: string[];
  reasons: string[];
  rule_ids: string[];
}

export interface HostCompletionReviewQueue {
  item: ReconciliationFinding | null;
  remaining: number;
}

export interface HostCompletionDecisionPayload {
  proposal_id: string;
  inventory_fingerprint: string;
  decision: ReconciliationDecision;
  target_host_id?: number;
  counterpart_ip?: string;
  counterpart_type?: "OS" | "BMC";
}

export interface HostCompletionDecisionResponse {
  id: number;
  decision: ReconciliationDecision;
  host_id: number | null;
  proposal_id: string;
  idempotent_replay: boolean;
}
