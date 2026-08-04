import { ApiError as SharedApiError, apiRequest } from "../shared/apiClient";
import type {
  AssetFormValues,
  AssetsResponse,
  BulkValues,
} from "./types";

export class IPAssetsApiError extends Error {
  constructor(public readonly messages: string[]) {
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
      onAuthenticationRequired: (loginUrl) => {
        authenticationRequired = true;
        window.location.assign(loginUrl);
      },
    });
  } catch (error) {
    if (!(error instanceof SharedApiError)) throw error;
    if (authenticationRequired) {
      throw new IPAssetsApiError(["Authentication required."]);
    }

    const detail = error.payload && typeof error.payload === "object"
      ? (error.payload as Record<string, unknown>).detail
      : undefined;
    const messages = typeof detail === "string" || Array.isArray(detail)
      ? error.messages
      : [`IP asset request failed (${error.status}).`];
    throw new IPAssetsApiError(messages);
  }
}

function assetPayload(values: AssetFormValues) {
  return {
    ip_address: values.ip_address.trim(),
    type: values.type,
    project_id: values.project_id ? Number(values.project_id) : null,
    host_id: values.host_id ? Number(values.host_id) : null,
    tags: values.tags,
    notes: values.notes,
  };
}

export function fetchAssets(url: string, signal?: AbortSignal) {
  return request<AssetsResponse>(url, { signal });
}

export function createAsset(endpoint: string, values: AssetFormValues) {
  return request<{ asset_id: number }>(endpoint, {
    method: "POST",
    json: assetPayload(values),
  });
}

export function updateAsset(
  endpoint: string,
  assetId: number,
  values: AssetFormValues,
) {
  const { ip_address: _ipAddress, ...payload } = assetPayload(values);
  return request<void>(`${endpoint}/${assetId}`, {
    method: "PATCH",
    json: payload,
  });
}

export function autoHostAsset(endpoint: string, assetId: number) {
  return request<{ host_id: number; host_name: string }>(
    `${endpoint}/${assetId}/auto-host`,
    { method: "POST" },
  );
}

export function deleteAsset(
  endpoint: string,
  assetId: number,
  acknowledged: boolean,
  confirmIp: string,
) {
  return request<void>(`${endpoint}/${assetId}`, {
    method: "DELETE",
    json: {
      acknowledged,
      confirm_ip: confirmIp,
    },
  });
}

export function bulkUpdateAssets(
  endpoint: string,
  assetIds: number[],
  values: BulkValues,
) {
  return request<{ updated_count: number }>(`${endpoint}/bulk`, {
    method: "POST",
    json: {
      asset_ids: assetIds,
      type: values.type || null,
      set_project: Boolean(values.projectMode),
      project_id:
        values.projectMode === "assign" && values.project_id
          ? Number(values.project_id)
          : null,
      tags_to_add: values.tags_to_add,
      tags_to_remove: values.tags_to_remove,
      notes_mode: values.notes_mode || null,
      notes: values.notes,
    },
  });
}
