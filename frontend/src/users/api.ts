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

async function readErrorMessages(response: Response): Promise<string[]> {
  try {
    const payload = (await response.json()) as {
      detail?: string | Array<{ msg?: string }>;
    };
    if (typeof payload.detail === "string") {
      return [payload.detail];
    }
    if (Array.isArray(payload.detail)) {
      return payload.detail
        .map((item) => item.msg?.replace(/^Value error,\s*/, "") ?? "")
        .filter(Boolean);
    }
  } catch {
    // Use the stable fallback below.
  }
  return [`User request failed (${response.status}).`];
}

async function request<T>(
  url: string,
  options: RequestInit = {},
): Promise<T> {
  const response = await fetch(url, {
    credentials: "same-origin",
    headers: {
      Accept: "application/json",
      ...(options.body ? { "Content-Type": "application/json" } : {}),
      ...options.headers,
    },
    ...options,
  });

  if (response.redirected && response.url.includes("/ui/login")) {
    window.location.assign("/ui/login?return_to=/ui/users");
    throw new ApiError("Authentication required.", ["Authentication required."], 401);
  }

  if (!response.ok) {
    const messages = await readErrorMessages(response);
    throw new ApiError(
      messages[0] ?? `User request failed (${response.status}).`,
      messages,
      response.status,
    );
  }

  if (response.status === 204) {
    return undefined as T;
  }
  return response.json() as Promise<T>;
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
    body: JSON.stringify(values),
  });
}

export function updateUser(
  endpoint: string,
  userId: number,
  values: EditUserValues,
): Promise<UserUpdateResponse> {
  return request<UserUpdateResponse>(`${endpoint}/${userId}`, {
    method: "PATCH",
    body: JSON.stringify(values),
  });
}

export function deleteUser(
  endpoint: string,
  userId: number,
  confirmUsername: string,
): Promise<void> {
  return request<void>(`${endpoint}/${userId}`, {
    method: "DELETE",
    body: JSON.stringify({ confirm_username: confirmUsername }),
  });
}
