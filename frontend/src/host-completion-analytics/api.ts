import { apiRequest } from "../shared/apiClient";
import type { HostCompletionAnalytics } from "./types";

export interface ManualRuleInput {
  source_prefix: string;
  target_prefix: string;
  active: boolean;
  notes: string | null;
}

export async function fetchHostCompletionAnalytics(
  endpoint: string,
): Promise<HostCompletionAnalytics> {
  return apiRequest<HostCompletionAnalytics>(endpoint);
}

export async function saveManualRule(
  input: ManualRuleInput,
  ruleId?: number,
): Promise<void> {
  await apiRequest(ruleId ? `/api/host-completion/rules/${ruleId}` : "/api/host-completion/rules", {
    method: ruleId ? "PUT" : "POST",
    json: input,
  });
}
