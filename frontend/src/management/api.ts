import { apiRequest } from "../shared/apiClient";
import type { ManagementOverview } from "./types";

export async function fetchManagementOverview(
  endpoint: string,
): Promise<ManagementOverview> {
  return apiRequest<ManagementOverview>(endpoint);
}
