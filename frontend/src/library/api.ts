import { ApiError as SharedApiError, apiRequest } from "../shared/apiClient";
import type { LibraryResponse } from "./types";

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
      onAuthenticationRequired: (loginUrl) => {
        authenticationRequired = true;
        window.location.assign(loginUrl);
      },
    });
  } catch (error) {
    if (!(error instanceof SharedApiError)) throw error;

    const detail = error.payload && typeof error.payload === "object"
      ? (error.payload as Record<string, unknown>).detail
      : undefined;
    const messages = authenticationRequired
      ? ["Authentication required."]
      : (typeof detail === "string" || Array.isArray(detail)) &&
          error.messages.length
        ? error.messages
        : [`Library request failed (${error.status})`];
    throw new ApiError(
      messages[0] ?? `Library request failed (${error.status})`,
      messages,
    );
  }
}

export function fetchLibraryItems<T>(
  endpoint: string,
  entity: string,
): Promise<LibraryResponse<T>> {
  return request<LibraryResponse<T>>(`${endpoint}/${entity}`);
}

export function createLibraryItem<T, V extends object = object>(
  endpoint: string,
  entity: string,
  values: V,
): Promise<T> {
  return request<T>(`${endpoint}/${entity}`, {
    method: "POST",
    json: values,
  });
}

export function updateLibraryItem<T, V extends object = object>(
  endpoint: string,
  entity: string,
  entityId: number,
  values: V,
): Promise<T> {
  return request<T>(`${endpoint}/${entity}/${entityId}`, {
    method: "PATCH",
    json: values,
  });
}

export function deleteLibraryItem(
  endpoint: string,
  entity: string,
  entityId: number,
  confirmName: string,
): Promise<void> {
  return request<void>(`${endpoint}/${entity}/${entityId}`, {
    method: "DELETE",
    json: { confirm_name: confirmName },
  });
}
