import { ApiError as SharedApiError, apiRequest } from "../shared/apiClient";
import type { DetailResponse, EditValues } from "./types";

export class IPAssetApiError extends Error {
  constructor(
    public readonly messages: string[],
    public readonly status?: number,
  ) {
    super(messages[0] ?? "IP asset request failed.");
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
        window.location.assign(
          `/ui/login?return_to=${window.location.pathname}`,
        );
      },
    });
  } catch (error) {
    if (!(error instanceof SharedApiError)) throw error;
    if (authenticationRequired) {
      throw new IPAssetApiError(["Authentication required."], 303);
    }

    const detail = error.payload && typeof error.payload === "object"
      ? (error.payload as Record<string, unknown>).detail
      : undefined;
    const messages = (typeof detail === "string" || Array.isArray(detail)) &&
        error.messages.length
      ? error.messages
      : [`IP asset request failed (${error.status}).`];
    throw new IPAssetApiError(messages, error.status);
  }
}

export function fetchIPAssetDetail(endpoint: string, signal?: AbortSignal) {
  return request<DetailResponse>(`${endpoint}/detail`, { signal });
}

export function updateIPAsset(endpoint: string, values: EditValues) {
  return request<void>(endpoint, {
    method: "PATCH",
    json: {
      type: values.type,
      project_id: values.project_id ? Number(values.project_id) : null,
      host_id: values.host_id ? Number(values.host_id) : null,
      tags: values.tags,
      notes: values.notes,
    },
  });
}

export function autoHostIPAsset(endpoint: string) {
  return request<{ host_id: number; host_name: string }>(`${endpoint}/auto-host`, {
    method: "POST",
  });
}

export function deleteIPAsset(
  endpoint: string,
  acknowledged: boolean,
  confirmIp: string,
) {
  return request<void>(endpoint, {
    method: "DELETE",
    json: {
      acknowledged,
      confirm_ip: confirmIp,
    },
  });
}
