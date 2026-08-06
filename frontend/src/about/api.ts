import { apiRequest } from "../shared/apiClient";
import type { AboutData } from "./types";

export async function fetchAboutData(endpoint: string): Promise<AboutData> {
  return apiRequest<AboutData>(endpoint);
}
