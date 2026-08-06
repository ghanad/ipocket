import { ApiError as SharedApiError, apiRequest } from "../shared/apiClient";
import type {
  CreateUserValues,
  EditUserValues,
  UserRow,
  UsersResponse,
  UserUpdateResponse,
} from "./types";

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly messages: string[],
    public readonly status: number,
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
        window.location.assign("/ui/login?return_to=/ui/users");
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
        : [`User request failed (${error.status}).`];
    throw new ApiError(
      messages[0] ?? `User request failed (${error.status}).`,
      messages,
      error.status,
    );
  }
}

export function fetchUsers(endpoint: string): Promise<UsersResponse> {
  return request<UsersResponse>(endpoint);
}

export function createUser(
  endpoint: string,
  values: CreateUserValues,
): Promise<UserRow> {
  return request<UserRow>(endpoint, {
    method: "POST",
    json: values,
  });
}

export function updateUser(
  endpoint: string,
  userId: number,
  values: EditUserValues,
): Promise<UserUpdateResponse> {
  return request<UserUpdateResponse>(`${endpoint}/${userId}`, {
    method: "PATCH",
    json: values,
  });
}

export function deleteUser(
  endpoint: string,
  userId: number,
  confirmUsername: string,
): Promise<void> {
  return request<void>(`${endpoint}/${userId}`, {
    method: "DELETE",
    json: { confirm_username: confirmUsername },
  });
}
