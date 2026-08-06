import { ApiError as SharedApiError, apiRequest } from "../shared/apiClient";
import type {
  AddressFormValues,
  RangeAddressesResponse,
} from "./types";

export class RangeAddressesApiError extends Error {
  constructor(public messages: string[]) {
    super(messages[0] ?? "Range address request failed.");
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

    let messages: string[];
    if (authenticationRequired) {
      messages = ["Authentication required."];
    } else if (error.payload && typeof error.payload === "object") {
      const detail = (error.payload as Record<string, unknown>).detail;
      messages = typeof detail === "string" || Array.isArray(detail)
        ? error.messages
        : [`Range address request failed (${error.status}).`];
    } else {
      messages = [`Range address request failed (${error.status}).`];
    }
    throw new RangeAddressesApiError(messages);
  }
}

export function fetchRangeAddresses(url: string, signal?: AbortSignal) {
  return request<RangeAddressesResponse>(url, { signal });
}

function body(values: AddressFormValues) {
  return {
    ip_address: values.ip_address,
    type: values.type,
    project_id: values.project_id ? Number(values.project_id) : null,
    tags: values.tags,
    notes: values.notes,
  };
}

export function createRangeAddress(
  endpoint: string,
  values: AddressFormValues,
) {
  return request<{ asset_id: number; ip_address: string }>(endpoint, {
    method: "POST",
    json: body(values),
  });
}

export function updateRangeAddress(
  endpoint: string,
  assetId: number,
  values: AddressFormValues,
) {
  const { ip_address: _ipAddress, ...payload } = body(values);
  return request<{ asset_id: number; ip_address: string }>(
    `${endpoint}/${assetId}`,
    { method: "PATCH", json: payload },
  );
}
