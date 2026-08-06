import { apiRequest } from "../shared/apiClient";
import type { HostCompletionAnalytics } from "./types";

export async function fetchHostCompletionAnalytics(
  endpoint: string,
): Promise<HostCompletionAnalytics> {
  return apiRequest<HostCompletionAnalytics>(endpoint);
}
