import { apiRequest } from "../shared/apiClient";
import type {
  HostCompletionDecisionPayload,
  HostCompletionDecisionResponse,
  HostCompletionReviewQueue,
} from "./types";

export function fetchHostCompletionReviewQueue(
  endpoint: string,
): Promise<HostCompletionReviewQueue> {
  return apiRequest<HostCompletionReviewQueue>(endpoint);
}

export function submitHostCompletionDecision(
  endpoint: string,
  payload: HostCompletionDecisionPayload,
): Promise<HostCompletionDecisionResponse> {
  return apiRequest<HostCompletionDecisionResponse>(endpoint, {
    method: "POST",
    json: payload,
    headers: {
      "Idempotency-Key": `${payload.proposal_id}:${payload.decision}`,
    },
  });
}
