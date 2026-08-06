import { ApiError, apiRequest } from "../shared/apiClient";
import type { HostDetailResponse } from "./types";

export class HostDetailApiError extends Error {
  constructor(
    message: string,
    public readonly status: number | null = null,
    public readonly loginUrl: string | null = null,
  ) {
    super(message);
  }
}

export async function fetchHostDetail(
  endpoint: string,
  signal?: AbortSignal,
): Promise<HostDetailResponse> {
  let loginUrl: string | null = null;
  try {
    return await apiRequest<HostDetailResponse>(endpoint, {
      signal,
      onAuthenticationRequired: () => {
        loginUrl = `/ui/login?return_to=${encodeURIComponent(window.location.pathname)}`;
      },
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") throw error;
    if (error instanceof ApiError) {
      if (error.status === 401 && loginUrl) {
        throw new HostDetailApiError("Authentication required.", 401, loginUrl);
      }
      if (error.status === 404) {
        throw new HostDetailApiError("Host not found.", 404);
      }
      throw new HostDetailApiError("Host details could not be loaded.", error.status);
    }
    throw new HostDetailApiError("Host details could not be loaded.");
  }
}
