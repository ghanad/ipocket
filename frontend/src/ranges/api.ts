import { ApiError as SharedApiError, apiRequest } from "../shared/apiClient";
import type {
  RangeFormValues,
  RangeRow,
  RangesResponse,
} from "./types";

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly messages: string[],
  ) {
    super(message);
  }
}

async function request<T>(
  url: string,
  options: Parameters<typeof apiRequest>[1] = {},
): Promise<T> {
  let authenticationRequired = false;
  try {
    return await apiRequest<T>(url, {
      ...options,
      onAuthenticationRequired: () => {
        authenticationRequired = true;
        window.location.assign("/ui/login?return_to=/ui/ranges");
      },
    });
  } catch (error) {
    if (!(error instanceof SharedApiError)) throw error;
    let messages: string[];
    if (authenticationRequired) {
      messages = ["Authentication required."];
    } else if (error.payload && typeof error.payload === "object") {
      const detail = (error.payload as Record<string, unknown>).detail;
      messages = typeof detail === "string" || Array.isArray(detail)
        ? error.messages
        : [`Range request failed (${error.status})`];
    } else {
      messages = [`Range request failed (${error.status})`];
    }
    throw new ApiError(
      messages[0] ?? `Range request failed (${error.status})`,
      messages,
    );
  }
}

export async function fetchRanges(endpoint: string): Promise<RangesResponse> {
  return request<RangesResponse>(endpoint);
}

export async function createRange(
  endpoint: string,
  values: RangeFormValues,
): Promise<RangeRow> {
  return request<RangeRow>(endpoint, {
    method: "POST",
    json: values,
  });
}

export async function updateRange(
  endpoint: string,
  rangeId: number,
  values: RangeFormValues,
): Promise<RangeRow> {
  return request<RangeRow>(`${endpoint}/${rangeId}`, {
    method: "PATCH",
    json: values,
  });
}

export async function deleteRange(
  endpoint: string,
  rangeId: number,
  confirmName: string,
): Promise<void> {
  return request<void>(`${endpoint}/${rangeId}`, {
    method: "DELETE",
    json: { confirm_name: confirmName },
  });
}
